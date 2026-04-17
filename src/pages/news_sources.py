from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/sources",
    name="News Sources",
    title="NewsLens | News Sources",
)


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(title=title, template="plotly_white", margin={"l": 30, "r": 20, "t": 60, "b": 40})
    return figure


def _source_count_figure(source_counts: list[dict], top_n: int) -> go.Figure:
    rows = source_counts[:top_n]
    if not rows:
        return _empty_figure("Article Volume by Source")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("source", "Unknown") for row in rows],
                y=[row.get("count", 0) for row in rows],
                marker_color="#0d6efd",
            )
        ]
    )
    figure.update_layout(title="Article Volume by Source", template="plotly_white")
    return figure


def _source_scoring_figure(score_status_rows: list[dict], top_n: int) -> go.Figure:
    rows = score_status_rows[:top_n]
    if not rows:
        return _empty_figure("Scoring Coverage by Source")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("source", "Unknown") for row in rows],
                y=[
                    ((int(row.get("scored", 0) or 0) / int(row.get("total", 0) or 1)) * 100.0)
                    if int(row.get("total", 0) or 0) > 0
                    else 0.0
                    for row in rows
                ],
                marker_color="#198754"
            )
        ]
    )
    figure.update_layout(title="Scoring Coverage by Source (%)", template="plotly_white")
    return figure


def _source_table(rows: list[dict], top_n: int):
    visible = rows[:top_n]
    if not visible:
        return dbc.Alert("No source summary available.", color="warning", className="mb-0")

    header = html.Thead(
        html.Tr(
            [
                html.Th("Source"),
                html.Th("Articles"),
                html.Th("Scored"),
                html.Th("Zero"),
                html.Th("Unscorable"),
                html.Th("Coverage %"),
            ]
        )
    )

    body_rows = []
    for row in visible:
        total = int(row.get("total", 0) or 0)
        scored = int(row.get("scored", 0) or 0)
        zero_score = int(row.get("zero_score", 0) or 0)
        unscorable = int(row.get("unscorable", 0) or 0)
        coverage = (scored / total * 100.0) if total > 0 else None
        body_rows.append(
            html.Tr(
                [
                    html.Td(row.get("source", "Unknown")),
                    html.Td(total),
                    html.Td(scored),
                    html.Td(zero_score),
                    html.Td(unscorable),
                    html.Td(f"{coverage:.1f}" if isinstance(coverage, (int, float)) else "n/a"),
                ]
            )
        )
    return dbc.Table(
        [header, html.Tbody(body_rows)],
        bordered=True,
        striped=True,
        hover=True,
        responsive=True,
        size="sm",
    )


layout = dbc.Container(
    [
        dcc.Interval(id="news-sources-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Sources", className="mb-3"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Data mode"),
                        dcc.Dropdown(
                            id="news-sources-mode",
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
                        dcc.Input(id="news-sources-snapshot-date", type="date", className="form-control", disabled=True),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Top N sources"),
                        dcc.Input(id="news-sources-top-n", type="number", min=3, max=50, step=1, value=12, className="form-control"),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-sources-refresh", color="secondary"),
                    ],
                    md=2,
                ),
                dbc.Col(html.Div(id="news-sources-status"), md=4),
            ],
            className="mb-3",
        ),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-sources-count-graph"), lg=7, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-sources-score-graph"), lg=5, className="mb-3"),
            ]
        ),
        dbc.Row([dbc.Col(html.Div(id="news-sources-table"), width=12)]),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-sources-status", "children"),
    Output("news-sources-count-graph", "figure"),
    Output("news-sources-score-graph", "figure"),
    Output("news-sources-table", "children"),
    Input("news-sources-load", "n_intervals"),
    Input("news-sources-refresh", "n_clicks"),
    State("news-sources-mode", "value"),
    State("news-sources-snapshot-date", "value"),
    State("news-sources-top-n", "value"),
)
def load_news_sources(_load_tick, _refresh_clicks, data_mode, snapshot_date, top_n):
    force_refresh = ctx.triggered_id == "news-sources-refresh"
    n_value = int(top_n) if isinstance(top_n, (int, float)) and top_n else 12
    n_value = max(3, min(50, n_value))

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
        return dbc.Alert(f"Stats error ({status_code}): {error}", color="danger"), empty, empty, dbc.Alert(
            "No source table data.", color="warning"
        )

    meta = payload.get("meta", {})
    derived = payload.get("data", {}).get("derived", {})
    source_counts = derived.get("source_counts", [])
    chart_aggregates = derived.get("chart_aggregates", {})
    score_status_by_source = chart_aggregates.get("score_status_by_source", [])

    return (
        build_status_alert(meta, leading_parts=[f"Sources: {len(source_counts)}"]),
        _source_count_figure(source_counts, n_value),
        _source_scoring_figure(score_status_by_source, n_value),
        _source_table(score_status_by_source, n_value),
    )


@callback(
    Output("news-sources-snapshot-date", "disabled"),
    Input("news-sources-mode", "value"),
)
def toggle_sources_snapshot_input(data_mode):
    return data_mode != "snapshot"
