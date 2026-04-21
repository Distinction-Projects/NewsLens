from urllib.parse import urlencode

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html
from flask import current_app

from src.pages.news_page_utils import build_status_alert


dash.register_page(
    __name__,
    path="/news/stats",
    name="News Stats",
    title="NewsLens | News Stats",
)


def _api_get(path: str, params: dict[str, str | int | None]) -> tuple[int, dict]:
    filtered = {key: value for key, value in params.items() if value not in (None, "", [])}
    query = urlencode(filtered, doseq=True)
    target = f"{path}?{query}" if query else path
    with current_app.test_client() as client:
        response = client.get(target)
    parsed = response.get_json(silent=True)
    if isinstance(parsed, dict):
        return response.status_code, parsed
    return response.status_code, {"status": "error", "error": response.get_data(as_text=True)}


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        title=title,
        template="plotly_white",
        margin={"l": 30, "r": 20, "t": 60, "b": 40},
    )
    return figure


def _source_figure(source_counts: list[dict]) -> go.Figure:
    if not source_counts:
        return _empty_figure("Articles by Source")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("source", "Unknown") for row in source_counts],
                y=[row.get("count", 0) for row in source_counts],
                marker_color="#0d6efd",
            )
        ]
    )
    figure.update_layout(title="Articles by Source", template="plotly_white")
    return figure


def _tag_figure(tag_counts: list[dict]) -> go.Figure:
    # Filter out 'general' tag and take top 12
    filtered_tags = [row for row in tag_counts if row.get("tag", "").lower() != "general"]
    top_tags = filtered_tags[:12]
    if not top_tags:
        return _empty_figure("Top Tags")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("count", 0) for row in top_tags],
                y=[row.get("tag", "") for row in top_tags],
                orientation="h",
                marker_color="#198754",
            )
        ]
    )
    figure.update_layout(title="Top Tags", template="plotly_white", yaxis={"autorange": "reversed"})
    return figure


def _score_figure(score_distribution: dict) -> go.Figure:
    bins = score_distribution.get("bins", []) if isinstance(score_distribution, dict) else []
    if not bins:
        return _empty_figure("Score Distribution")
    figure = go.Figure(
        data=[
            go.Bar(
                x=[row.get("label", "") for row in bins],
                y=[row.get("count", 0) for row in bins],
                marker_color="#6f42c1",
            )
        ]
    )
    figure.update_layout(title="Score Distribution (%)", template="plotly_white")
    return figure


def _daily_figure(daily_counts: list[dict]) -> go.Figure:
    if not daily_counts:
        return _empty_figure("Daily Article Count (UTC)")
    figure = go.Figure(
        data=[
            go.Scatter(
                x=[row.get("date", "") for row in daily_counts],
                y=[row.get("count", 0) for row in daily_counts],
                mode="lines+markers",
                line={"color": "#fd7e14"},
            )
        ]
    )
    figure.update_layout(title="Daily Article Count (UTC)", template="plotly_white")
    return figure


def _summary_cards(derived: dict) -> list:
    score_coverage_ratio = derived.get("score_coverage_ratio")
    ratio_text = f"{score_coverage_ratio * 100:.1f}%" if isinstance(score_coverage_ratio, (int, float)) else "n/a"
    total_articles = derived.get("total_articles", 0)
    scored_articles = derived.get("scored_articles", 0)
    zero_score_articles = derived.get("zero_score_articles", 0)
    unscorable_articles = derived.get("unscorable_articles")
    if not isinstance(unscorable_articles, int):
        if isinstance(total_articles, int) and isinstance(scored_articles, int):
            unscorable_articles = max(total_articles - scored_articles, 0)
        else:
            unscorable_articles = "n/a"

    cards = [
        ("Total Articles", total_articles, "primary"),
        ("Scored Articles", scored_articles, "info"),
        ("Zero Scores", zero_score_articles if isinstance(zero_score_articles, int) else "n/a", "secondary"),
        ("Unscorable", unscorable_articles, "warning"),
        ("Score Coverage", ratio_text, "success"),
    ]
    return [
        dbc.Col(
            dbc.Card(
                dbc.CardBody([html.P(label, className="text-muted mb-1"), html.H4(str(value), className="mb-0")]),
                color=color,
                inverse=False,
                className="shadow-sm",
            ),
            md=2,
            className="mb-3",
        )
        for label, value, color in cards
    ]


layout = dbc.Container(
    [
        dcc.Interval(id="news-stats-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Statistics", className="mb-3"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Data mode"),
                        dcc.Dropdown(
                            id="news-stats-data-mode",
                            options=[
                                {"label": "Current", "value": "current"},
                                {"label": "Snapshot", "value": "snapshot"},
                            ],
                            value="current",
                            clearable=False,
                        ),
                    ],
                    md=3,
                    className="mb-3",
                ),
                dbc.Col(
                    [
                        dbc.Label("Snapshot date (UTC)"),
                        dcc.Input(
                            id="news-stats-snapshot-date",
                            type="date",
                            className="form-control",
                            disabled=True,
                        ),
                    ],
                    md=3,
                    className="mb-3",
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh Stats", id="news-stats-refresh", color="secondary", className="mb-3"),
                    ],
                    md=2,
                    className="mb-3",
                ),
                dbc.Col(html.Div(id="news-stats-status"), md=4, className="mb-3"),
            ]
        ),
        dbc.Row(id="news-stats-cards"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-source-graph"), lg=6, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-tag-graph"), lg=6, className="mb-3"),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-score-graph"), lg=6, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-daily-graph"), lg=6, className="mb-3"),
            ]
        ),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-stats-status", "children"),
    Output("news-stats-cards", "children"),
    Output("news-source-graph", "figure"),
    Output("news-tag-graph", "figure"),
    Output("news-score-graph", "figure"),
    Output("news-daily-graph", "figure"),
    Input("news-stats-load", "n_intervals"),
    Input("news-stats-refresh", "n_clicks"),
    State("news-stats-data-mode", "value"),
    State("news-stats-snapshot-date", "value"),
)
def load_news_stats(_load_tick, _refresh_clicks, data_mode, snapshot_date):
    force_refresh = ctx.triggered_id == "news-stats-refresh"
    snapshot_date_param = snapshot_date if data_mode == "snapshot" else None
    status_code, payload = _api_get(
        "/api/news/stats",
        {
            "refresh": "true" if force_refresh else None,
            "snapshot_date": snapshot_date_param,
        },
    )

    if status_code != 200:
        error_text = payload.get("error", "Unknown error")
        error = dbc.Alert(f"Stats error ({status_code}): {error_text}", color="danger")
        empty = _empty_figure("No data")
        return error, _summary_cards({}), empty, empty, empty, empty

    meta = payload.get("meta", {})
    data = payload.get("data", {})
    derived = data.get("derived", {})
    status_component = build_status_alert(meta, leading_parts=[f"Schema: {meta.get('schema_version')}"])

    source_counts = derived.get("source_counts", [])
    tag_counts = derived.get("tag_counts", [])
    score_distribution = derived.get("score_distribution", {})
    daily_counts = derived.get("daily_counts_utc", [])

    return (
        status_component,
        _summary_cards(derived),
        _source_figure(source_counts),
        _tag_figure(tag_counts),
        _score_figure(score_distribution),
        _daily_figure(daily_counts),
    )


@callback(
    Output("news-stats-snapshot-date", "disabled"),
    Input("news-stats-data-mode", "value"),
)
def toggle_stats_snapshot_input(data_mode):
    return data_mode != "snapshot"
