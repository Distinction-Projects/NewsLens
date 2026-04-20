from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/source-effects",
    name="News Source Effects",
    title="NewsLens | News Source Effects",
)


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(title=title, template="plotly_white", margin={"l": 30, "r": 20, "t": 60, "b": 40})
    return figure


def _as_rows(source_lens_effects: dict) -> list[dict]:
    rows = source_lens_effects.get("rows") if isinstance(source_lens_effects, dict) else None
    return rows if isinstance(rows, list) else []


def _source_topic_rows(data: dict) -> list[dict]:
    if not isinstance(data, dict):
        return []
    derived = data.get("derived") if isinstance(data.get("derived"), dict) else {}
    topic_control = derived.get("source_topic_control") if isinstance(derived.get("source_topic_control"), dict) else {}
    topics = topic_control.get("topics") if isinstance(topic_control.get("topics"), list) else []
    return [topic for topic in topics if isinstance(topic, dict)]


def _select_source_reliability_view(data: dict, analysis_mode: str, selected_topic: str | None) -> dict:
    if not isinstance(data, dict):
        return {}
    derived = data.get("derived") if isinstance(data.get("derived"), dict) else {}
    source_reliability = derived.get("source_reliability") if isinstance(derived.get("source_reliability"), dict) else {}
    pooled = source_reliability.get("pooled") if isinstance(source_reliability.get("pooled"), dict) else {}
    if analysis_mode != "within_topic" or not isinstance(selected_topic, str):
        return pooled
    topic_rows = source_reliability.get("topics") if isinstance(source_reliability.get("topics"), list) else []
    for topic_row in topic_rows:
        if not isinstance(topic_row, dict):
            continue
        topic = str(topic_row.get("topic") or "").strip()
        if topic != selected_topic:
            continue
        assessment = topic_row.get("assessment")
        return assessment if isinstance(assessment, dict) else {}
    return pooled


def _reliability_status_parts(reliability: dict) -> list[str]:
    if not isinstance(reliability, dict) or not reliability:
        return []
    tier = str(reliability.get("tier") or "n/a")
    status = str(reliability.get("status") or "missing")
    score = reliability.get("score")
    if isinstance(score, (int, float)):
        summary = f"Reliability: {tier} ({float(score):.2f})"
    else:
        summary = f"Reliability: {tier}"
    parts = [summary, f"Reliability status: {status}"]
    flags = reliability.get("flags") if isinstance(reliability.get("flags"), list) else []
    if flags:
        parts.append(f"Reliability flags: {len(flags)}")
    return parts


def _topic_options(topic_rows: list[dict]) -> list[dict]:
    options: list[dict] = []
    for row in topic_rows:
        topic = str(row.get("topic") or "").strip()
        if not topic:
            continue
        n_articles = row.get("n_articles")
        if isinstance(n_articles, int):
            label = f"{topic} (n={n_articles})"
        else:
            label = topic
        options.append({"label": label, "value": topic})
    return options


def _select_source_effects_view(
    data: dict,
    analysis_mode: str,
    selected_topic: str | None,
) -> tuple[dict, str, list[dict], str | None, bool]:
    derived = data.get("derived") if isinstance(data.get("derived"), dict) else {}
    pooled_effects = derived.get("source_lens_effects") if isinstance(derived.get("source_lens_effects"), dict) else {}
    topic_rows = _source_topic_rows(data)
    options = _topic_options(topic_rows)
    option_values = {str(option.get("value")) for option in options}
    topic_value = selected_topic if isinstance(selected_topic, str) and selected_topic in option_values else None
    if topic_value is None and options:
        first = options[0].get("value")
        topic_value = str(first) if isinstance(first, str) else None

    within_topic_enabled = analysis_mode == "within_topic" and topic_value is not None
    if within_topic_enabled:
        selected_row = next((row for row in topic_rows if str(row.get("topic") or "") == topic_value), None)
        topic_effects = (
            selected_row.get("source_lens_effects")
            if isinstance(selected_row, dict) and isinstance(selected_row.get("source_lens_effects"), dict)
            else {}
        )
        return topic_effects, f"within-topic ({topic_value})", options, topic_value, False

    if analysis_mode == "within_topic" and not options:
        return pooled_effects, "pooled (topic-confounded; no topics available)", options, None, True
    return pooled_effects, "pooled (topic-confounded)", options, topic_value, True


def _filtered_rows(rows: list[dict], max_lenses: int, p_threshold: float | None) -> list[dict]:
    filtered: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        p_perm_fdr = row.get("p_perm_fdr")
        p_perm = row.get("p_perm")
        candidate = p_perm_fdr if isinstance(p_perm_fdr, (int, float)) else p_perm
        if isinstance(p_threshold, (int, float)) and p_threshold < 1.0:
            if not isinstance(candidate, (int, float)) or float(candidate) > float(p_threshold):
                continue
        filtered.append(row)
    return filtered[:max_lenses]


def _summary_cards(source_lens_effects: dict, rows: list[dict]) -> list:
    status = source_lens_effects.get("status") if isinstance(source_lens_effects, dict) else "n/a"
    permutations = source_lens_effects.get("permutations") if isinstance(source_lens_effects, dict) else 0
    multiple_testing = (
        source_lens_effects.get("multiple_testing")
        if isinstance(source_lens_effects, dict) and isinstance(source_lens_effects.get("multiple_testing"), dict)
        else {}
    )
    n_tests = multiple_testing.get("n_tests", 0)
    best_q = "n/a"
    best_p = "n/a"
    if rows:
        q_values = [float(row.get("p_perm_fdr")) for row in rows if isinstance(row.get("p_perm_fdr"), (int, float))]
        p_values = [float(row.get("p_perm_raw")) for row in rows if isinstance(row.get("p_perm_raw"), (int, float))]
        if q_values:
            best_q = f"{min(q_values):.4f}"
        if p_values:
            best_p = f"{min(p_values):.4f}"
    cards = [
        ("Status", status),
        ("Permutation Runs", permutations),
        ("Tests (FDR family)", n_tests),
        ("Lenses Tested", len(rows)),
        ("Best q-value (FDR)", best_q),
        ("Best raw p-value", best_p),
    ]
    return [
        dbc.Col(
            dbc.Card(
                dbc.CardBody([html.P(label, className="text-muted mb-1"), html.H4(str(value), className="mb-0")]),
                className="shadow-sm",
            ),
            md=6,
            lg=2,
            className="mb-3",
        )
        for label, value in cards
    ]


def _effects_figure(rows: list[dict]) -> go.Figure:
    if not rows:
        return _empty_figure("Lens Source Effect Sizes (eta^2)")

    lenses = [str(row.get("lens", "")) for row in rows]
    eta_sq = [float(row.get("eta_sq") or 0.0) for row in rows]
    p_values_raw = [f"{float(row.get('p_perm_raw')):.4f}" if isinstance(row.get("p_perm_raw"), (int, float)) else "n/a" for row in rows]
    p_values_fdr = [f"{float(row.get('p_perm_fdr')):.4f}" if isinstance(row.get("p_perm_fdr"), (int, float)) else "n/a" for row in rows]
    figure = go.Figure(
        data=[
            go.Bar(
                x=lenses,
                y=eta_sq,
                marker_color="#198754",
                customdata=list(zip(p_values_raw, p_values_fdr)),
                hovertemplate=(
                    "Lens: %{x}<br>eta^2: %{y:.4f}<br>"
                    "p_perm_raw: %{customdata[0]}<br>"
                    "p_perm_fdr: %{customdata[1]}<extra></extra>"
                ),
            )
        ]
    )
    figure.update_layout(
        title="Lens Source Effect Sizes (eta^2)",
        template="plotly_white",
        xaxis_title="Lens",
        yaxis_title="eta^2",
    )
    return figure


def _source_mean_figure(selected_row: dict | None) -> go.Figure:
    if not isinstance(selected_row, dict):
        return _empty_figure("Source Mean Lens Percent")

    source_means = selected_row.get("source_means")
    if not isinstance(source_means, dict) or not source_means:
        return _empty_figure("Source Mean Lens Percent")

    ordered = sorted(
        ((str(name), float(value)) for name, value in source_means.items() if isinstance(value, (int, float))),
        key=lambda item: item[1],
        reverse=True,
    )
    if not ordered:
        return _empty_figure("Source Mean Lens Percent")

    figure = go.Figure(
        data=[
            go.Bar(
                x=[item[0] for item in ordered],
                y=[item[1] for item in ordered],
                marker_color="#0d6efd",
                hovertemplate="Source: %{x}<br>Mean Lens %: %{y:.1f}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        title=f"Source Means for {selected_row.get('lens', 'selected lens')}",
        template="plotly_white",
        xaxis_title="Source",
        yaxis_title="Mean Lens %",
    )
    return figure


def _results_table(rows: list[dict]):
    if not rows:
        return dbc.Alert("No source-effect rows matched the current filter.", color="warning", className="mb-0")

    table_rows = []
    for row in rows:
        table_rows.append(
            html.Tr(
                [
                    html.Td(str(row.get("lens", ""))),
                    html.Td(str(row.get("n", "n/a"))),
                    html.Td(str(row.get("n_sources", "n/a"))),
                    html.Td(f"{float(row.get('eta_sq')):.4f}" if isinstance(row.get("eta_sq"), (int, float)) else "n/a"),
                    html.Td(f"{float(row.get('p_perm_raw')):.4f}" if isinstance(row.get("p_perm_raw"), (int, float)) else "n/a"),
                    html.Td(f"{float(row.get('p_perm_fdr')):.4f}" if isinstance(row.get("p_perm_fdr"), (int, float)) else "n/a"),
                    html.Td(f"{float(row.get('f_stat')):.3f}" if isinstance(row.get("f_stat"), (int, float)) else "n/a"),
                    html.Td(str(row.get("top_source") or "n/a")),
                    html.Td(str(row.get("bottom_source") or "n/a")),
                    html.Td(f"{float(row.get('source_gap')):.2f}" if isinstance(row.get("source_gap"), (int, float)) else "n/a"),
                ]
            )
        )

    return dbc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Lens"),
                        html.Th("n"),
                        html.Th("Sources"),
                        html.Th("eta^2"),
                        html.Th("p_perm_raw"),
                        html.Th("p_perm_fdr"),
                        html.Th("F"),
                        html.Th("Top Source"),
                        html.Th("Bottom Source"),
                        html.Th("Gap"),
                    ]
                )
            ),
            html.Tbody(table_rows),
        ],
        bordered=True,
        striped=True,
        hover=True,
        responsive=True,
        size="sm",
    )


layout = dbc.Container(
    [
        dcc.Interval(id="news-source-effects-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Source Effects", className="mb-2"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    html.P(
                        "Lens-level one-way source tests (ANOVA-style) built from article lens percentages, "
                        "with pooled and within-topic views for confound-aware comparisons.",
                        className="text-muted",
                    ),
                    width=12,
                )
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Data mode"),
                        dcc.Dropdown(
                            id="news-source-effects-mode",
                            options=[
                                {"label": "Current", "value": "current"},
                                {"label": "Snapshot", "value": "snapshot"},
                            ],
                            value="current",
                            clearable=False,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Snapshot date (UTC)"),
                        dcc.Input(id="news-source-effects-snapshot-date", type="date", className="form-control", disabled=True),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Analysis scope"),
                        dcc.Dropdown(
                            id="news-source-effects-analysis-mode",
                            options=[
                                {"label": "Pooled (topic-confounded)", "value": "pooled"},
                                {"label": "Within-topic", "value": "within_topic"},
                            ],
                            value="pooled",
                            clearable=False,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Topic"),
                        dcc.Dropdown(id="news-source-effects-topic", options=[], value=None, clearable=False, disabled=True),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Lenses shown"),
                        dcc.Dropdown(
                            id="news-source-effects-max-lenses",
                            options=[{"label": str(n), "value": n} for n in (5, 10, 15, 20)],
                            value=10,
                            clearable=False,
                        ),
                    ],
                    md=1,
                ),
                dbc.Col(
                    [
                        dbc.Label("Max q-value (FDR)"),
                        dcc.Dropdown(
                            id="news-source-effects-p-threshold",
                            options=[
                                {"label": "All", "value": 1.0},
                                {"label": "0.10", "value": 0.10},
                                {"label": "0.05", "value": 0.05},
                                {"label": "0.01", "value": 0.01},
                            ],
                            value=1.0,
                            clearable=False,
                        ),
                    ],
                    md=1,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-source-effects-refresh", color="secondary"),
                    ],
                    md=2,
                ),
            ],
            className="mb-3",
        ),
        dbc.Row([dbc.Col(html.Div(id="news-source-effects-status"), width=12)], className="mb-3"),
        dbc.Row(id="news-source-effects-cards"),
        dbc.Row([dbc.Col(dcc.Graph(id="news-source-effects-bar"), width=12, className="mb-3")]),
        dbc.Row([dbc.Col(html.Div(id="news-source-effects-table"), width=12, className="mb-3")]),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Lens detail"),
                        dcc.Dropdown(id="news-source-effects-lens", options=[], value=None, clearable=False),
                    ],
                    md=4,
                    className="mb-3",
                ),
            ]
        ),
        dbc.Row([dbc.Col(dcc.Graph(id="news-source-effects-source-means"), width=12)]),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-source-effects-status", "children"),
    Output("news-source-effects-cards", "children"),
    Output("news-source-effects-bar", "figure"),
    Output("news-source-effects-table", "children"),
    Output("news-source-effects-topic", "options"),
    Output("news-source-effects-topic", "value"),
    Output("news-source-effects-topic", "disabled"),
    Output("news-source-effects-lens", "options"),
    Output("news-source-effects-lens", "value"),
    Output("news-source-effects-source-means", "figure"),
    Input("news-source-effects-load", "n_intervals"),
    Input("news-source-effects-refresh", "n_clicks"),
    Input("news-source-effects-analysis-mode", "value"),
    Input("news-source-effects-max-lenses", "value"),
    Input("news-source-effects-p-threshold", "value"),
    State("news-source-effects-lens", "value"),
    State("news-source-effects-mode", "value"),
    State("news-source-effects-snapshot-date", "value"),
    State("news-source-effects-topic", "value"),
)
def load_news_source_effects(
    _load_tick,
    _refresh_clicks,
    analysis_mode,
    max_lenses,
    p_threshold,
    selected_lens,
    data_mode,
    snapshot_date,
    selected_topic,
):
    force_refresh = ctx.triggered_id == "news-source-effects-refresh"
    status_code, payload = api_get(
        "/api/news/stats",
        {
            "snapshot_date": snapshot_param(data_mode, snapshot_date),
            "refresh": "true" if force_refresh else None,
        },
    )

    if status_code != 200:
        error = payload.get("error", "Unknown error")
        alert = dbc.Alert(f"Stats error ({status_code}): {error}", color="danger")
        empty = _empty_figure("No data")
        return alert, _summary_cards({}, []), empty, alert, [], None, True, [], None, empty

    meta = payload.get("meta", {})
    data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
    source_lens_effects, scope_label, topic_options, topic_value, topic_disabled = _select_source_effects_view(
        data,
        str(analysis_mode or "pooled"),
        selected_topic,
    )
    reliability = _select_source_reliability_view(data, str(analysis_mode or "pooled"), topic_value)
    rows = _as_rows(source_lens_effects)

    max_lens_count = int(max_lenses) if isinstance(max_lenses, (int, float)) else 10
    threshold = float(p_threshold) if isinstance(p_threshold, (int, float)) else 1.0
    shown_rows = _filtered_rows(rows, max_lens_count, threshold)
    status_text = str(source_lens_effects.get("status") or "missing")
    reason = str(source_lens_effects.get("reason") or "").strip()
    permutations = source_lens_effects.get("permutations", 0)

    leading_parts = [
        f"Scope: {scope_label}",
        f"Source-effects status: {status_text}",
        f"Rows shown: {len(shown_rows)}",
        f"Permutations: {permutations}",
    ]
    multiple_testing = source_lens_effects.get("multiple_testing") if isinstance(source_lens_effects.get("multiple_testing"), dict) else {}
    method = str(multiple_testing.get("method") or "").strip()
    n_tests = multiple_testing.get("n_tests")
    if method:
        leading_parts.append(f"Multiple-testing: {method} (n_tests={n_tests if isinstance(n_tests, int) else 'n/a'})")
    if reason:
        leading_parts.append(f"Reason: {reason}")
    leading_parts.extend(_reliability_status_parts(reliability))
    status_alert = build_status_alert(meta, leading_parts=leading_parts)

    options = [{"label": str(row.get("lens", "")), "value": str(row.get("lens", ""))} for row in shown_rows if row.get("lens")]
    option_values = {option["value"] for option in options}
    selected_value = selected_lens if selected_lens in option_values else (options[0]["value"] if options else None)
    selected_row = next((row for row in shown_rows if row.get("lens") == selected_value), None)

    return (
        status_alert,
        _summary_cards(source_lens_effects, rows),
        _effects_figure(shown_rows),
        _results_table(shown_rows),
        topic_options,
        topic_value,
        topic_disabled,
        options,
        selected_value,
        _source_mean_figure(selected_row),
    )


@callback(
    Output("news-source-effects-snapshot-date", "disabled"),
    Input("news-source-effects-mode", "value"),
)
def toggle_source_effects_snapshot_input(data_mode):
    return data_mode != "snapshot"
