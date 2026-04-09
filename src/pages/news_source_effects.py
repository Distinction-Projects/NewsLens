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


def _filtered_rows(rows: list[dict], max_lenses: int, p_threshold: float | None) -> list[dict]:
    filtered: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        p_perm = row.get("p_perm")
        if isinstance(p_threshold, (int, float)) and p_threshold < 1.0:
            if not isinstance(p_perm, (int, float)) or float(p_perm) > float(p_threshold):
                continue
        filtered.append(row)
    return filtered[:max_lenses]


def _summary_cards(source_lens_effects: dict, rows: list[dict]) -> list:
    status = source_lens_effects.get("status") if isinstance(source_lens_effects, dict) else "n/a"
    permutations = source_lens_effects.get("permutations") if isinstance(source_lens_effects, dict) else 0
    cards = [
        ("Status", status),
        ("Permutation Runs", permutations),
        ("Lenses Tested", len(rows)),
        ("Best p-value", f"{float(rows[0]['p_perm']):.4f}" if rows and isinstance(rows[0].get("p_perm"), (int, float)) else "n/a"),
    ]
    return [
        dbc.Col(
            dbc.Card(
                dbc.CardBody([html.P(label, className="text-muted mb-1"), html.H4(str(value), className="mb-0")]),
                className="shadow-sm",
            ),
            md=6,
            lg=3,
            className="mb-3",
        )
        for label, value in cards
    ]


def _effects_figure(rows: list[dict]) -> go.Figure:
    if not rows:
        return _empty_figure("Lens Source Effect Sizes (eta^2)")

    lenses = [str(row.get("lens", "")) for row in rows]
    eta_sq = [float(row.get("eta_sq") or 0.0) for row in rows]
    p_values = [
        (f"{float(row.get('p_perm')):.4f}" if isinstance(row.get("p_perm"), (int, float)) else "n/a")
        for row in rows
    ]
    figure = go.Figure(
        data=[
            go.Bar(
                x=lenses,
                y=eta_sq,
                marker_color="#198754",
                customdata=p_values,
                hovertemplate="Lens: %{x}<br>eta^2: %{y:.4f}<br>p_perm: %{customdata}<extra></extra>",
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
                    html.Td(f"{float(row.get('p_perm')):.4f}" if isinstance(row.get("p_perm"), (int, float)) else "n/a"),
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
                        html.Th("p_perm"),
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
                        "with permutation p-values and source-mean effect summaries.",
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
                        dbc.Label("Lenses shown"),
                        dcc.Dropdown(
                            id="news-source-effects-max-lenses",
                            options=[{"label": str(n), "value": n} for n in (5, 10, 15, 20)],
                            value=10,
                            clearable=False,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Max p-value"),
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
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-source-effects-refresh", color="secondary"),
                    ],
                    md=1,
                ),
                dbc.Col(html.Div(id="news-source-effects-status"), md=3),
            ],
            className="mb-3",
        ),
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
    Output("news-source-effects-lens", "options"),
    Output("news-source-effects-lens", "value"),
    Output("news-source-effects-source-means", "figure"),
    Input("news-source-effects-load", "n_intervals"),
    Input("news-source-effects-refresh", "n_clicks"),
    Input("news-source-effects-max-lenses", "value"),
    Input("news-source-effects-p-threshold", "value"),
    State("news-source-effects-lens", "value"),
    State("news-source-effects-mode", "value"),
    State("news-source-effects-snapshot-date", "value"),
)
def load_news_source_effects(_load_tick, _refresh_clicks, max_lenses, p_threshold, selected_lens, data_mode, snapshot_date):
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
        return alert, _summary_cards({}, []), empty, alert, [], None, empty

    meta = payload.get("meta", {})
    derived = payload.get("data", {}).get("derived", {})
    source_lens_effects = derived.get("source_lens_effects", {}) if isinstance(derived, dict) else {}
    rows = _as_rows(source_lens_effects)

    max_lens_count = int(max_lenses) if isinstance(max_lenses, (int, float)) else 10
    threshold = float(p_threshold) if isinstance(p_threshold, (int, float)) else 1.0
    shown_rows = _filtered_rows(rows, max_lens_count, threshold)
    status_text = str(source_lens_effects.get("status") or "missing")
    reason = str(source_lens_effects.get("reason") or "").strip()
    permutations = source_lens_effects.get("permutations", 0)

    leading_parts = [
        f"Source-effects status: {status_text}",
        f"Rows shown: {len(shown_rows)}",
        f"Permutations: {permutations}",
    ]
    if reason:
        leading_parts.append(f"Reason: {reason}")
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
