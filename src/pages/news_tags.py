from __future__ import annotations

from collections import Counter

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/tags",
    name="News Tags",
    title="NewsLens | News Tags",
)


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(title=title, template="plotly_white", margin={"l": 30, "r": 20, "t": 60, "b": 40})
    return figure


def _top_tags_figure(tag_counts: list[dict], top_n: int) -> go.Figure:
    rows = tag_counts[:top_n]
    if not rows:
        return _empty_figure("Top Tags")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("count", 0) for row in rows],
                y=[row.get("tag", "") for row in rows],
                orientation="h",
                marker_color="#fd7e14",
            )
        ]
    )
    figure.update_layout(title="Top Tags", template="plotly_white", yaxis={"autorange": "reversed"})
    return figure


def _tag_count_distribution_figure(tag_distribution: list[dict]) -> go.Figure:
    if not tag_distribution:
        return _empty_figure("Tag Count Distribution")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("label", "") for row in tag_distribution],
                y=[row.get("count", 0) for row in tag_distribution],
                marker_color="#6f42c1",
            )
        ]
    )
    figure.update_layout(title="Tags per Article Distribution", template="plotly_white")
    return figure


def _source_tag_heatmap(source_tag_matrix: list[dict], top_sources: int = 10, top_tags: int = 12) -> go.Figure:
    if not source_tag_matrix:
        return _empty_figure("Source x Tag Intensity")

    source_counter: Counter[str] = Counter()
    tag_counter: Counter[str] = Counter()
    for row in source_tag_matrix:
        source = str(row.get("source", "Unknown"))
        tag = str(row.get("tag", ""))
        count = int(row.get("count", 0) or 0)
        source_counter[source] += count
        tag_counter[tag] += count

    source_labels = [name for name, _ in source_counter.most_common(top_sources)]
    tag_labels = [name for name, _ in tag_counter.most_common(top_tags)]
    if not source_labels or not tag_labels:
        return _empty_figure("Source x Tag Intensity")

    value_map = {(str(row.get("source", "Unknown")), str(row.get("tag", ""))): int(row.get("count", 0) or 0) for row in source_tag_matrix}
    z_values = []
    for source in source_labels:
        z_values.append([value_map.get((source, tag), 0) for tag in tag_labels])

    figure = go.Figure(
        data=[
            go.Heatmap(
                z=z_values,
                x=tag_labels,
                y=source_labels,
                colorscale="Blues",
            )
        ]
    )
    figure.update_layout(title="Source x Tag Intensity", template="plotly_white")
    return figure


layout = dbc.Container(
    [
        dcc.Interval(id="news-tags-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Tags", className="mb-3"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Data mode"),
                        dcc.Dropdown(
                            id="news-tags-mode",
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
                        dcc.Input(id="news-tags-snapshot-date", type="date", className="form-control", disabled=True),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Top N tags"),
                        dcc.Input(id="news-tags-top-n", type="number", min=5, max=40, step=1, value=15, className="form-control"),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-tags-refresh", color="secondary"),
                    ],
                    md=2,
                ),
                dbc.Col(html.Div(id="news-tags-status"), md=4),
            ],
            className="mb-3",
        ),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-tags-top-graph"), lg=5, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-tags-dist-graph"), lg=3, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-tags-heatmap"), lg=4, className="mb-3"),
            ]
        ),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-tags-status", "children"),
    Output("news-tags-top-graph", "figure"),
    Output("news-tags-dist-graph", "figure"),
    Output("news-tags-heatmap", "figure"),
    Input("news-tags-load", "n_intervals"),
    Input("news-tags-refresh", "n_clicks"),
    State("news-tags-mode", "value"),
    State("news-tags-snapshot-date", "value"),
    State("news-tags-top-n", "value"),
)
def load_news_tags(_load_tick, _refresh_clicks, data_mode, snapshot_date, top_n):
    force_refresh = ctx.triggered_id == "news-tags-refresh"
    n_value = int(top_n) if isinstance(top_n, (int, float)) and top_n else 15
    n_value = max(5, min(40, n_value))
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
        return dbc.Alert(f"Stats error ({status_code}): {error}", color="danger"), empty, empty, empty

    meta = payload.get("meta", {})
    derived = payload.get("data", {}).get("derived", {})
    chart_aggregates = derived.get("chart_aggregates", {})
    tag_counts = derived.get("tag_counts", [])
    tag_distribution = chart_aggregates.get("tag_count_distribution", [])
    source_tag_matrix = chart_aggregates.get("source_tag_matrix", [])

    return (
        build_status_alert(meta, leading_parts=[f"Unique tags: {len(tag_counts)}"]),
        _top_tags_figure(tag_counts, n_value),
        _tag_count_distribution_figure(tag_distribution),
        _source_tag_heatmap(source_tag_matrix),
    )


@callback(
    Output("news-tags-snapshot-date", "disabled"),
    Input("news-tags-mode", "value"),
)
def toggle_tags_snapshot_input(data_mode):
    return data_mode != "snapshot"
