from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_news_intro, build_status_alert, snapshot_param


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


def _scoring_status_source_figure(score_status_rows: list[dict], top_n: int = 12) -> go.Figure:
    rows = score_status_rows[:top_n]
    if not rows:
        return _empty_figure("Scoring Status by Source")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("source", "Unknown") for row in rows],
                y=[int(row.get("unscorable", 0) or 0) for row in rows],
                marker_color="#dc3545",
                name="Unscorable",
            ),
            go.Bar(
                x=[row.get("source", "Unknown") for row in rows],
                y=[int(row.get("zero_score", 0) or 0) for row in rows],
                marker_color="#6c757d",
                name="Zero (Lens-Level)",
            ),
            go.Bar(
                x=[row.get("source", "Unknown") for row in rows],
                y=[int(row.get("scored", 0) or 0) for row in rows],
                marker_color="#198754",
                name="Scored",
            )
        ]
    )
    figure.update_layout(title="Scoring Status by Source", template="plotly_white", barmode="group")
    return figure


def _scored_source_figure(scored_by_source: list[dict], top_n: int = 12) -> go.Figure:
    rows = scored_by_source[:top_n]
    if not rows:
        return _empty_figure("Scored Articles by Source")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("source", "Unknown") for row in rows],
                y=[row.get("count", 0) for row in rows],
                marker_color="#dc3545",
            )
        ]
    )
    figure.update_layout(title="Scored Articles by Source", template="plotly_white")
    return figure


def _score_tag_heatmap_figure(heatmap_rows: list[dict]) -> go.Figure:
    if not heatmap_rows:
        return _empty_figure("Tag Count Distribution")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("label", "") for row in heatmap_rows],
                y=[int(row.get("count", 0) or 0) for row in heatmap_rows],
                marker_color="#0d6efd",
            )
        ]
    )
    figure.update_layout(title="Tag Count Distribution", xaxis_title="Tags per Article", yaxis_title="Articles", template="plotly_white")
    return figure


def _score_cards(derived: dict) -> list:
    score_coverage_ratio = derived.get("score_coverage_ratio")
    scored_articles = derived.get("scored_articles", 0)
    zero_score_articles = derived.get("zero_score_articles", 0)
    unscorable_articles = derived.get("unscorable_articles", "n/a")
    score_object_missing_articles = derived.get("score_object_missing_articles", "n/a")
    cards = [
        ("Scored Articles", scored_articles),
        ("Zero Scores", zero_score_articles if isinstance(zero_score_articles, int) else "n/a"),
        ("Unscorable", unscorable_articles if isinstance(unscorable_articles, int) else "n/a"),
        (
            "Missing Score Objects",
            score_object_missing_articles if isinstance(score_object_missing_articles, int) else "n/a",
        ),
        (
            "Score Coverage",
            f"{score_coverage_ratio * 100:.1f}%"
            if isinstance(score_coverage_ratio, (int, float))
            else "n/a",
        ),
    ]
    return [
        dbc.Col(
            dbc.Card(
                dbc.CardBody([html.P(label, className="text-white mb-1"), html.H4(str(value), className="mb-0")]),
                className="shadow-sm",
            ),
            md=2,
            className="mb-3",
        )
        for label, value in cards
    ]


layout = dbc.Container(
    [
        dcc.Interval(id="news-score-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Score Lab", className="mb-3"), width=12)]),
        build_news_intro(
            "Run focused scoring diagnostics and inspect model-output behavior."
        ),
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
    score_status_by_source = chart_aggregates.get("score_status_by_source", [])
    scored_by_source = chart_aggregates.get("scored_by_source", [])
    tag_count_distribution = chart_aggregates.get("tag_count_distribution", [])

    return (
        build_status_alert(
            meta,
            leading_parts=[
                f"Scored: {derived.get('scored_articles', 0)}",
                f"Unscorable: {derived.get('unscorable_articles', 0)}",
            ],
        ),
        _score_cards(derived),
        _scoring_status_source_figure(score_status_by_source),
        _scored_source_figure(scored_by_source),
        _score_tag_heatmap_figure(tag_count_distribution),
    )


@callback(
    Output("news-score-snapshot-date", "disabled"),
    Input("news-score-mode", "value"),
)
def toggle_score_snapshot_input(data_mode):
    return data_mode != "snapshot"
