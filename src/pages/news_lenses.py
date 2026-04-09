from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/lenses",
    name="News Lenses",
    title="NewsLens | News Lenses",
)


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(title=title, template="plotly_white", margin={"l": 30, "r": 20, "t": 60, "b": 40})
    return figure


def _coverage_percent(items_with_scores: object, items_total: object) -> float | None:
    if not isinstance(items_with_scores, (int, float)) or not isinstance(items_total, (int, float)) or items_total <= 0:
        return None
    return (float(items_with_scores) / float(items_total)) * 100.0


def _lens_capacity_figure(lenses: list[dict]) -> go.Figure:
    if not lenses:
        return _empty_figure("Lens Maximum Score Capacity")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("name", "Unknown") for row in lenses],
                y=[row.get("max_total", 0) or 0 for row in lenses],
                marker_color="#0d6efd",
            )
        ]
    )
    figure.update_layout(title="Lens Maximum Score Capacity", template="plotly_white")
    return figure


def _lens_coverage_figure(lenses: list[dict], items_total: object) -> go.Figure:
    if not lenses:
        return _empty_figure("Lens Coverage")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("name", "Unknown") for row in lenses],
                y=[_coverage_percent(row.get("items_with_scores"), items_total) or 0 for row in lenses],
                marker_color="#198754",
            )
        ]
    )
    figure.update_layout(title="Lens Coverage Across Articles (%)", template="plotly_white", yaxis={"range": [0, 100]})
    return figure


def _lens_cards(lens_summary: dict) -> list:
    lenses = lens_summary.get("lenses", []) if isinstance(lens_summary, dict) else []
    max_totals = [float(row.get("max_total")) for row in lenses if isinstance(row.get("max_total"), (int, float))]
    rubric_counts = [int(row.get("rubric_count")) for row in lenses if isinstance(row.get("rubric_count"), (int, float))]
    cards = [
        ("Tracked Lenses", len(lenses)),
        ("Items Total", lens_summary.get("items_total", 0)),
        ("Aggregation", lens_summary.get("aggregation", "n/a")),
        ("Avg Rubrics / Lens", f"{(sum(rubric_counts) / len(rubric_counts)):.1f}" if rubric_counts else "n/a"),
        ("Avg Max Score", f"{(sum(max_totals) / len(max_totals)):.1f}" if max_totals else "n/a"),
    ]
    return [
        dbc.Col(
            dbc.Card(
                dbc.CardBody([html.P(label, className="text-muted mb-1"), html.H4(str(value), className="mb-0")]),
                className="shadow-sm",
            ),
            md=4,
            lg=2,
            className="mb-3",
        )
        for label, value in cards
    ]


def _lens_table(lenses: list[dict], items_total: object):
    if not lenses:
        return dbc.Alert("No upstream lens summary is available.", color="warning", className="mb-0")

    header = html.Thead(
        html.Tr(
            [
                html.Th("Lens"),
                html.Th("Rubrics"),
                html.Th("Max Total"),
                html.Th("Items With Scores"),
                html.Th("Coverage %"),
            ]
        )
    )
    body_rows = []
    for row in lenses:
        coverage = _coverage_percent(row.get("items_with_scores"), items_total)
        body_rows.append(
            html.Tr(
                [
                    html.Td(row.get("name", "Unknown")),
                    html.Td(row.get("rubric_count", "n/a")),
                    html.Td(f"{float(row.get('max_total')):.1f}" if isinstance(row.get("max_total"), (int, float)) else "n/a"),
                    html.Td(row.get("items_with_scores", "n/a")),
                    html.Td(f"{coverage:.1f}" if isinstance(coverage, (int, float)) else "n/a"),
                ]
            )
        )
    return dbc.Table([header, html.Tbody(body_rows)], bordered=True, striped=True, hover=True, responsive=True, size="sm")


layout = dbc.Container(
    [
        dcc.Interval(id="news-lenses-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Lenses", className="mb-2"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    html.P(
                        "This page surfaces the upstream lens inventory that powers the multi-lens scoring pipeline. "
                        "It is a direct view over the published analysis bundle rather than a local reconstruction.",
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
                            id="news-lenses-mode",
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
                        dcc.Input(id="news-lenses-snapshot-date", type="date", className="form-control", disabled=True),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-lenses-refresh", color="secondary"),
                    ],
                    md=2,
                ),
                dbc.Col(html.Div(id="news-lenses-status"), md=4),
            ],
            className="mb-3",
        ),
        dbc.Row(id="news-lenses-cards"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-lenses-capacity-graph"), lg=6, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-lenses-coverage-graph"), lg=6, className="mb-3"),
            ]
        ),
        dbc.Row([dbc.Col(html.Div(id="news-lenses-table"), width=12)]),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-lenses-status", "children"),
    Output("news-lenses-cards", "children"),
    Output("news-lenses-capacity-graph", "figure"),
    Output("news-lenses-coverage-graph", "figure"),
    Output("news-lenses-table", "children"),
    Input("news-lenses-load", "n_intervals"),
    Input("news-lenses-refresh", "n_clicks"),
    State("news-lenses-mode", "value"),
    State("news-lenses-snapshot-date", "value"),
)
def load_news_lenses(_load_tick, _refresh_clicks, data_mode, snapshot_date):
    force_refresh = ctx.triggered_id == "news-lenses-refresh"
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
        return dbc.Alert(f"Stats error ({status_code}): {error}", color="danger"), _lens_cards({}), empty, empty, dbc.Alert(
            "No lens summary data.", color="warning"
        )

    meta = payload.get("meta", {})
    analysis = payload.get("data", {}).get("analysis", {})
    lens_summary = analysis.get("lens_summary", {}) if isinstance(analysis, dict) else {}
    lenses = lens_summary.get("lenses", []) if isinstance(lens_summary, dict) else []
    items_total = lens_summary.get("items_total") if isinstance(lens_summary, dict) else None

    return (
        build_status_alert(meta, leading_parts=[f"Lenses: {len(lenses)}"]),
        _lens_cards(lens_summary),
        _lens_capacity_figure(lenses),
        _lens_coverage_figure(lenses, items_total),
        _lens_table(lenses, items_total),
    )


@callback(
    Output("news-lenses-snapshot-date", "disabled"),
    Input("news-lenses-mode", "value"),
)
def toggle_lenses_snapshot_input(data_mode):
    return data_mode != "snapshot"
