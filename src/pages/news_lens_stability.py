from __future__ import annotations

import statistics
from collections import defaultdict

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/lens-stability",
    name="News Lens Stability",
    title="NewsLens | News Lens Stability",
)


METRIC_OPTIONS = [
    {"label": "Std Dev", "value": "stddev"},
    {"label": "Coeff. of Variation", "value": "cv_percent"},
    {"label": "Source Mean Gap", "value": "source_gap"},
    {"label": "Value Range", "value": "range"},
]


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(title=title, template="plotly_white", margin={"l": 30, "r": 20, "t": 60, "b": 40})
    return figure


def _lens_max_map(lens_summary: dict) -> dict[str, float]:
    lenses = lens_summary.get("lenses", []) if isinstance(lens_summary, dict) else []
    result: dict[str, float] = {}
    for row in lenses:
        name = row.get("name")
        max_total = row.get("max_total")
        if isinstance(name, str) and isinstance(max_total, (int, float)) and max_total > 0:
            result[name] = float(max_total)
    return result


def _full_score_lens_scores(article: dict) -> dict[str, float]:
    score = article.get("score")
    if not isinstance(score, dict):
        return {}
    lens_scores = score.get("lens_scores")
    if not isinstance(lens_scores, dict):
        return {}

    normalized_scores: dict[str, float] = {}
    for lens_name, payload in lens_scores.items():
        if not isinstance(lens_name, str) or not isinstance(payload, dict):
            continue
        percent = payload.get("percent")
        if isinstance(percent, (int, float)):
            normalized_scores[lens_name] = float(percent)
            continue
        value = payload.get("value")
        max_value = payload.get("max_value")
        if isinstance(value, (int, float)) and isinstance(max_value, (int, float)) and max_value > 0:
            normalized_scores[lens_name] = (float(value) / float(max_value)) * 100.0
    return normalized_scores


def _legacy_high_score_lens_scores(article: dict, lens_maxima: dict[str, float]) -> dict[str, float]:
    high_score = article.get("high_score")
    if not isinstance(high_score, dict):
        return {}
    lens_scores = high_score.get("lens_scores")
    if not isinstance(lens_scores, dict):
        return {}

    normalized_scores: dict[str, float] = {}
    for lens_name, value in lens_scores.items():
        if not isinstance(lens_name, str) or not isinstance(value, (int, float)):
            continue
        max_total = lens_maxima.get(lens_name)
        if isinstance(max_total, (int, float)) and max_total > 0:
            normalized_scores[lens_name] = (float(value) / float(max_total)) * 100.0
        else:
            normalized_scores[lens_name] = float(value)
    return normalized_scores


def _lens_stability_rows(articles: list[dict], lens_maxima: dict[str, float]) -> tuple[list[dict], str]:
    lens_values: dict[str, list[float]] = defaultdict(list)
    lens_source_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    data_modes: set[str] = set()

    for article in articles:
        lens_scores = _full_score_lens_scores(article)
        row_mode = "full"
        if not lens_scores:
            lens_scores = _legacy_high_score_lens_scores(article, lens_maxima)
            row_mode = "legacy"
        if not lens_scores:
            continue

        data_modes.add(row_mode)
        source = article.get("source") if isinstance(article.get("source"), dict) else {}
        source_name = str(source.get("name") or "Unknown")

        for lens_name, value in lens_scores.items():
            if not isinstance(value, (int, float)):
                continue
            percent = float(value)
            lens_values[lens_name].append(percent)
            lens_source_values[lens_name][source_name].append(percent)

    rows: list[dict] = []
    for lens_name, values in lens_values.items():
        if not values:
            continue
        mean_value = statistics.fmean(values)
        stddev = statistics.pstdev(values) if len(values) > 1 else 0.0
        min_value = min(values)
        max_value = max(values)
        source_means = [
            statistics.fmean(source_values)
            for source_values in lens_source_values[lens_name].values()
            if source_values
        ]
        source_gap = (max(source_means) - min(source_means)) if len(source_means) >= 2 else 0.0
        rows.append(
            {
                "lens": lens_name,
                "count": len(values),
                "mean": mean_value,
                "stddev": stddev,
                "cv_percent": (stddev / mean_value) * 100.0 if mean_value > 0 else None,
                "min": min_value,
                "max": max_value,
                "range": max_value - min_value,
                "source_count": len(source_means),
                "source_gap": source_gap,
            }
        )

    rows.sort(key=lambda row: (float(row.get("stddev") or 0.0), float(row.get("range") or 0.0)), reverse=True)
    if not rows:
        coverage = "no lens data"
    elif data_modes == {"full"}:
        coverage = "all scored articles"
    elif data_modes == {"legacy"}:
        coverage = "high-score fallback"
    else:
        coverage = "mixed"
    return rows, coverage


def _summary_cards(rows: list[dict], lens_summary: dict | None = None) -> list:
    summary = lens_summary if isinstance(lens_summary, dict) else {}
    lenses_analyzed = (
        int(summary.get("stability_lens_count"))
        if isinstance(summary.get("stability_lens_count"), (int, float))
        else len(rows)
    )
    avg_stddev = summary.get("stability_avg_stddev")
    if not isinstance(avg_stddev, (int, float)):
        avg_stddev = statistics.fmean([float(row["stddev"]) for row in rows]) if rows else None
    top_lens = str(summary.get("stability_top_lens")) if isinstance(summary.get("stability_top_lens"), str) else (rows[0]["lens"] if rows else "n/a")
    total_samples = (
        int(summary.get("stability_total_samples"))
        if isinstance(summary.get("stability_total_samples"), (int, float))
        else sum(int(row.get("count") or 0) for row in rows)
    )
    cards = [
        ("Lenses Analyzed", lenses_analyzed),
        ("Avg Std Dev", f"{avg_stddev:.2f}" if isinstance(avg_stddev, (int, float)) else "n/a"),
        ("Most Volatile Lens", top_lens),
        ("Total Lens-Item Samples", total_samples),
    ]
    return [
        dbc.Col(
            dbc.Card(
                dbc.CardBody([html.P(label, className="text-muted mb-1"), html.H4(str(value), className="mb-0")]),
                className="shadow-sm",
            ),
            md=3,
            className="mb-3",
        )
        for label, value in cards
    ]


def _stability_scatter(rows: list[dict]) -> go.Figure:
    if not rows:
        return _empty_figure("Lens Stability: Mean vs Std Dev")
    figure = go.Figure(
        data=[
            go.Scatter(
                x=[float(row["mean"]) for row in rows],
                y=[float(row["stddev"]) for row in rows],
                mode="markers+text",
                text=[row["lens"] for row in rows],
                textposition="top center",
                marker={
                    "size": [max(10.0, float(row.get("count") or 0) * 1.5) for row in rows],
                    "color": [float(row.get("source_gap") or 0.0) for row in rows],
                    "colorscale": "Viridis",
                    "showscale": True,
                    "colorbar": {"title": "Source Gap"},
                },
                hovertemplate=(
                    "Lens: %{text}<br>"
                    "Mean: %{x:.2f}<br>"
                    "Std Dev: %{y:.2f}<br>"
                    "Samples: %{marker.size:.0f}<extra></extra>"
                ),
            )
        ]
    )
    figure.update_layout(
        title="Lens Stability: Mean vs Std Dev",
        template="plotly_white",
        xaxis_title="Mean Lens %",
        yaxis_title="Std Dev",
    )
    return figure


def _metric_bar(rows: list[dict], metric: str, top_n: int) -> go.Figure:
    if not rows:
        return _empty_figure("Top Lenses by Metric")
    metric_key = metric if metric in {"stddev", "cv_percent", "source_gap", "range"} else "stddev"
    ranked = sorted(
        rows,
        key=lambda row: float(row.get(metric_key) or 0.0),
        reverse=True,
    )[:top_n]
    if not ranked:
        return _empty_figure("Top Lenses by Metric")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row["lens"] for row in ranked],
                y=[float(row.get(metric_key) or 0.0) for row in ranked],
                marker_color="#dc3545",
            )
        ]
    )
    figure.update_layout(
        title=f"Top Lenses by {next(option['label'] for option in METRIC_OPTIONS if option['value'] == metric_key)}",
        template="plotly_white",
    )
    return figure


def _stability_table(rows: list[dict], metric: str, top_n: int):
    if not rows:
        return dbc.Alert("No lens stability data is available.", color="warning", className="mb-0")
    metric_key = metric if metric in {"stddev", "cv_percent", "source_gap", "range"} else "stddev"
    ranked = sorted(
        rows,
        key=lambda row: float(row.get(metric_key) or 0.0),
        reverse=True,
    )[:top_n]

    table_rows = []
    for row in ranked:
        table_rows.append(
            html.Tr(
                [
                    html.Td(row["lens"]),
                    html.Td(row["count"]),
                    html.Td(f"{float(row['mean']):.2f}"),
                    html.Td(f"{float(row['stddev']):.2f}"),
                    html.Td(f"{float(row['cv_percent']):.2f}" if isinstance(row.get("cv_percent"), (int, float)) else "n/a"),
                    html.Td(f"{float(row['source_gap']):.2f}"),
                    html.Td(f"{float(row['range']):.2f}"),
                ]
            )
        )
    return dbc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Lens"),
                        html.Th("Samples"),
                        html.Th("Mean"),
                        html.Th("Std Dev"),
                        html.Th("CV %"),
                        html.Th("Source Gap"),
                        html.Th("Range"),
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
        dcc.Interval(id="news-lens-stability-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Lens Stability", className="mb-2"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    html.P(
                        "This page estimates lens volatility and dispersion from article-level lens percentages, "
                        "including source-level spread.",
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
                            id="news-lens-stability-mode",
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
                        dcc.Input(id="news-lens-stability-snapshot-date", type="date", className="form-control", disabled=True),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Ranking Metric"),
                        dcc.Dropdown(id="news-lens-stability-metric", options=METRIC_OPTIONS, value="stddev", clearable=False),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        dbc.Label("Top N lenses"),
                        dcc.Input(id="news-lens-stability-top-n", type="number", min=3, max=30, step=1, value=10, className="form-control"),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-lens-stability-refresh", color="secondary"),
                    ],
                    md=1,
                ),
                dbc.Col(html.Div(id="news-lens-stability-status"), md=2),
            ],
            className="mb-3",
        ),
        dbc.Row(id="news-lens-stability-cards"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-lens-stability-scatter"), lg=7, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-lens-stability-metric-graph"), lg=5, className="mb-3"),
            ]
        ),
        dbc.Row([dbc.Col(html.Div(id="news-lens-stability-table"), width=12)]),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-lens-stability-status", "children"),
    Output("news-lens-stability-cards", "children"),
    Output("news-lens-stability-scatter", "figure"),
    Output("news-lens-stability-metric-graph", "figure"),
    Output("news-lens-stability-table", "children"),
    Input("news-lens-stability-load", "n_intervals"),
    Input("news-lens-stability-refresh", "n_clicks"),
    Input("news-lens-stability-metric", "value"),
    State("news-lens-stability-mode", "value"),
    State("news-lens-stability-snapshot-date", "value"),
    State("news-lens-stability-top-n", "value"),
)
def load_news_lens_stability(_load_tick, _refresh_clicks, metric, data_mode, snapshot_date, top_n):
    force_refresh = ctx.triggered_id == "news-lens-stability-refresh"
    n_value = int(top_n) if isinstance(top_n, (int, float)) and top_n else 10
    n_value = max(3, min(30, n_value))
    common_params = {
        "snapshot_date": snapshot_param(data_mode, snapshot_date),
        "refresh": "true" if force_refresh else None,
    }
    stats_code, stats_payload = api_get("/api/news/stats", common_params)

    if stats_code != 200:
        stats_error = stats_payload.get("error", "Unknown error")
        empty = _empty_figure("No data")
        alert = dbc.Alert(
            f"Lens stability data error: stats={stats_code} ({stats_error})",
            color="danger",
        )
        return alert, _summary_cards([]), empty, empty, alert

    meta = stats_payload.get("meta", {})
    derived = stats_payload.get("data", {}).get("derived", {})
    lens_views = derived.get("lens_views", {}) if isinstance(derived, dict) else {}
    rows = lens_views.get("stability_rows", []) if isinstance(lens_views.get("stability_rows"), list) else []
    coverage_mode = str(lens_views.get("coverage_mode") or "no lens data")
    lens_summary = lens_views.get("summary", {}) if isinstance(lens_views.get("summary"), dict) else {}
    lenses_analyzed = (
        int(lens_summary.get("stability_lens_count"))
        if isinstance(lens_summary.get("stability_lens_count"), (int, float))
        else len(rows)
    )

    return (
        build_status_alert(meta, leading_parts=[f"Lenses analyzed: {lenses_analyzed}", f"Coverage: {coverage_mode}"]),
        _summary_cards(rows, lens_summary),
        _stability_scatter(rows),
        _metric_bar(rows, str(metric or "stddev"), n_value),
        _stability_table(rows, str(metric or "stddev"), n_value),
    )


@callback(
    Output("news-lens-stability-snapshot-date", "disabled"),
    Input("news-lens-stability-mode", "value"),
)
def toggle_lens_stability_snapshot_input(data_mode):
    return data_mode != "snapshot"
