from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/score-lab",
    name="News Score Lab",
    title="NewsLens | News Score Lab",
)


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(title=title, template="plotly_white", margin={"l": 30, "r": 20, "t": 60, "b": 40})
    return figure


def _score_histogram_figure(histogram_bins: list[dict]) -> go.Figure:
    if not histogram_bins:
        return _empty_figure("Score Histogram (%)")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("label", "") for row in histogram_bins],
                y=[row.get("count", 0) for row in histogram_bins],
                marker_color="#6f42c1",
            )
        ]
    )
    figure.update_layout(title="Score Histogram (%)", template="plotly_white")
    return figure


def _high_score_source_figure(high_score_by_source: list[dict], top_n: int = 12) -> go.Figure:
    rows = high_score_by_source[:top_n]
    if not rows:
        return _empty_figure("High Scores by Source")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("source", "Unknown") for row in rows],
                y=[row.get("count", 0) for row in rows],
                marker_color="#dc3545",
            )
        ]
    )
    figure.update_layout(title="High Scores by Source", template="plotly_white")
    return figure


def _score_tag_heatmap_figure(heatmap_rows: list[dict]) -> go.Figure:
    if not heatmap_rows:
        return _empty_figure("Score Bin x Tag Count Bin")

    score_bins = sorted({str(row.get("score_bin", "")) for row in heatmap_rows})
    tag_bins = sorted({str(row.get("tag_count_bin", "")) for row in heatmap_rows})
    value_map = {(str(row.get("tag_count_bin", "")), str(row.get("score_bin", ""))): int(row.get("count", 0) or 0) for row in heatmap_rows}

    z_values = []
    for tag_bin in tag_bins:
        z_values.append([value_map.get((tag_bin, score_bin), 0) for score_bin in score_bins])

    figure = go.Figure(
        data=[
            go.Heatmap(
                z=z_values,
                x=score_bins,
                y=tag_bins,
                colorscale="Viridis",
            )
        ]
    )
    figure.update_layout(title="Score Bin x Tag Count Bin", xaxis_title="Score Bin", yaxis_title="Tag Count Bin", template="plotly_white")
    return figure


def _score_cards(derived: dict) -> list:
    distribution = derived.get("score_distribution", {}) if isinstance(derived, dict) else {}
    average = distribution.get("average_percent")
    high_ratio = derived.get("high_score_ratio")
    cards = [
        ("Scored Articles", derived.get("scored_articles", 0)),
        ("Average Score %", f"{average:.1f}" if isinstance(average, (int, float)) else "n/a"),
        ("High-Score Articles", derived.get("high_scoring_articles", 0)),
        ("High-Score Ratio", f"{high_ratio * 100:.1f}%" if isinstance(high_ratio, (int, float)) else "n/a"),
    ]
    return [
        dbc.Col(
            dbc.Card(
                dbc.CardBody([html.P(label, className="text-white mb-1"), html.H4(str(value), className="mb-0")]),
                className="shadow-sm",
            ),
            md=3,
            className="mb-3",
        )
        for label, value in cards
    ]


layout = dbc.Container(
    [
        dcc.Interval(id="news-score-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Score Lab", className="mb-3"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Data mode"),
                        dcc.Dropdown(
                            id="news-score-mode",
                            options=[
                                {"label": "Current", "value": "current"},
                                {"label": "Snapshot", "value": "snapshot"},
                            ],
                            value="current",
                            clearable=False,
                        ),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        dbc.Label("Snapshot date (UTC)"),
                        dcc.Input(id="news-score-snapshot-date", type="date", className="form-control", disabled=True),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-score-refresh", color="secondary"),
                    ],
                    md=2,
                ),
                dbc.Col(html.Div(id="news-score-status"), md=4),
            ],
            className="mb-3",
        ),
        dbc.Row(id="news-score-cards"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-score-histogram"), lg=5, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-score-high-source"), lg=3, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-score-heatmap"), lg=4, className="mb-3"),
            ]
        ),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-score-status", "children"),
    Output("news-score-cards", "children"),
    Output("news-score-histogram", "figure"),
    Output("news-score-high-source", "figure"),
    Output("news-score-heatmap", "figure"),
    Input("news-score-load", "n_intervals"),
    Input("news-score-refresh", "n_clicks"),
    State("news-score-mode", "value"),
    State("news-score-snapshot-date", "value"),
)
def load_news_score_lab(_load_tick, _refresh_clicks, data_mode, snapshot_date):
    force_refresh = ctx.triggered_id == "news-score-refresh"
    status_code, payload = api_get(
        "/api/news/stats",
        {
            "snapshot_date": snapshot_param(data_mode, snapshot_date),
            "refresh": "true" if force_refresh else None,
        },
    )

    if status_code != 200:
        error = payload.get("error", "Unknown error")
        empty = _empty_figure("No data")
        return dbc.Alert(f"Stats error ({status_code}): {error}", color="danger"), _score_cards({}), empty, empty, empty

    meta = payload.get("meta", {})
    derived = payload.get("data", {}).get("derived", {})
    chart_aggregates = derived.get("chart_aggregates", {})
    histogram_bins = chart_aggregates.get("score_histogram_bins", [])
    high_score_by_source = chart_aggregates.get("high_score_by_source", [])
    score_tag_heatmap = chart_aggregates.get("score_tag_count_heatmap", [])

    return (
        build_status_alert(meta, leading_parts=[f"Scored: {derived.get('scored_articles', 0)}"]),
        _score_cards(derived),
        _score_histogram_figure(histogram_bins),
        _high_score_source_figure(high_score_by_source),
        _score_tag_heatmap_figure(score_tag_heatmap),
    )


@callback(
    Output("news-score-snapshot-date", "disabled"),
    Input("news-score-mode", "value"),
)
def toggle_score_snapshot_input(data_mode):
    return data_mode != "snapshot"
