from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/trends",
    name="News Trends",
    title="NewsLens | News Trends",
)


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(title=title, template="plotly_white", margin={"l": 30, "r": 20, "t": 60, "b": 40})
    return figure


def _daily_trend_figure(daily_counts: list[dict]) -> go.Figure:
    if not daily_counts:
        return _empty_figure("Daily Articles (UTC)")
    figure = go.Figure(
        data=[
            go.Scatter(
                x=[row.get("date") for row in daily_counts],
                y=[row.get("count", 0) for row in daily_counts],
                mode="lines+markers",
                line={"color": "#0d6efd", "width": 2},
            )
        ]
    )
    figure.update_layout(title="Daily Articles (UTC)", template="plotly_white")
    return figure


def _publish_hour_figure(hour_counts: list[dict]) -> go.Figure:
    if not hour_counts:
        return _empty_figure("Publish Hour Distribution (UTC)")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("hour", 0) for row in hour_counts],
                y=[row.get("count", 0) for row in hour_counts],
                marker_color="#198754",
            )
        ]
    )
    figure.update_layout(title="Publish Hour Distribution (UTC)", xaxis_title="Hour", template="plotly_white")
    return figure


def _summary_cards(derived: dict) -> list:
    daily_counts = derived.get("daily_counts_utc", []) if isinstance(derived, dict) else []
    earliest = daily_counts[0].get("date") if daily_counts else "n/a"
    latest = daily_counts[-1].get("date") if daily_counts else "n/a"
    cards = [
        ("Articles", derived.get("total_articles", 0), "primary"),
        ("Days Covered", len(daily_counts), "info"),
        ("Earliest Day", earliest, "secondary"),
        ("Latest Day", latest, "success"),
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
        for label, value, _color in cards
    ]


layout = dbc.Container(
    [
        dcc.Interval(id="news-trends-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Trends", className="mb-3"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Data mode"),
                        dcc.Dropdown(
                            id="news-trends-mode",
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
                        dcc.Input(id="news-trends-snapshot-date", type="date", className="form-control", disabled=True),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-trends-refresh", color="secondary"),
                    ],
                    md=2,
                ),
                dbc.Col(html.Div(id="news-trends-status"), md=4),
            ],
            className="mb-3",
        ),
        dbc.Row(id="news-trends-cards"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-trends-daily-graph"), lg=8, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-trends-hour-graph"), lg=4, className="mb-3"),
            ]
        ),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-trends-status", "children"),
    Output("news-trends-cards", "children"),
    Output("news-trends-daily-graph", "figure"),
    Output("news-trends-hour-graph", "figure"),
    Input("news-trends-load", "n_intervals"),
    Input("news-trends-refresh", "n_clicks"),
    State("news-trends-mode", "value"),
    State("news-trends-snapshot-date", "value"),
)
def load_news_trends(_load_tick, _refresh_clicks, data_mode, snapshot_date):
    force_refresh = ctx.triggered_id == "news-trends-refresh"
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
        return dbc.Alert(f"Stats error ({status_code}): {error}", color="danger"), _summary_cards({}), empty, empty

    meta = payload.get("meta", {})
    derived = payload.get("data", {}).get("derived", {})
    chart_aggregates = derived.get("chart_aggregates", {})
    daily_counts = derived.get("daily_counts_utc", [])
    hour_counts = chart_aggregates.get("publish_hour_counts_utc", [])

    return (
        build_status_alert(meta, leading_parts=[f"Articles: {derived.get('total_articles', 0)}"]),
        _summary_cards(derived),
        _daily_trend_figure(daily_counts),
        _publish_hour_figure(hour_counts),
    )


@callback(
    Output("news-trends-snapshot-date", "disabled"),
    Input("news-trends-mode", "value"),
)
def toggle_trends_snapshot_input(data_mode):
    return data_mode != "snapshot"
