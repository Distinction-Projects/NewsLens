from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get


dash.register_page(
    __name__,
    path="/news/snapshot-compare",
    name="News Snapshot Compare",
    title="NewsLens | News Snapshot Compare",
)


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(title=title, template="plotly_white", margin={"l": 30, "r": 20, "t": 60, "b": 40})
    return figure


def _extract_metrics(payload: dict) -> dict:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    derived = data.get("derived") if isinstance(data.get("derived"), dict) else {}
    source_counts = derived.get("source_counts") if isinstance(derived.get("source_counts"), list) else []
    tag_counts = derived.get("tag_counts") if isinstance(derived.get("tag_counts"), list) else []
    daily_counts = derived.get("daily_counts_utc") if isinstance(derived.get("daily_counts_utc"), list) else []
    score_coverage_ratio = derived.get("score_coverage_ratio")
    return {
        "generated_at": meta.get("generated_at"),
        "total_articles": derived.get("total_articles"),
        "scored_articles": derived.get("scored_articles"),
        "zero_score_articles": derived.get("zero_score_articles"),
        "unscorable_articles": derived.get("unscorable_articles"),
        "score_coverage_ratio_percent": (
            score_coverage_ratio * 100.0
            if isinstance(score_coverage_ratio, (int, float))
            else None
        ),
        "source_count": len(source_counts),
        "tag_count": len(tag_counts),
        "days_covered": len(daily_counts),
    }


def _metric_cards(current_metrics: dict, snapshot_metrics: dict) -> list:
    metrics = [
        ("Total Articles", "total_articles"),
        ("Scored Articles", "scored_articles"),
        ("Zero Scores", "zero_score_articles"),
        ("Unscorable", "unscorable_articles"),
        ("Score Coverage %", "score_coverage_ratio_percent"),
        ("Source Count", "source_count"),
        ("Tag Count", "tag_count"),
        ("Days Covered", "days_covered"),
    ]

    cards = []
    for label, key in metrics:
        current_value = current_metrics.get(key)
        snapshot_value = snapshot_metrics.get(key)
        if isinstance(current_value, (int, float)) and isinstance(snapshot_value, (int, float)):
            delta = current_value - snapshot_value
            delta_text = f"{delta:+.1f}" if isinstance(delta, float) and not float(delta).is_integer() else f"{int(delta):+d}"
        else:
            delta_text = "n/a"

        def _fmt(value):
            if isinstance(value, float):
                return f"{value:.1f}"
            if isinstance(value, int):
                return str(value)
            return "n/a"

        cards.append(
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.P(label, className="text-muted mb-1"),
                            html.H5(f"Current: {_fmt(current_value)}", className="mb-1"),
                            html.H6(f"Snapshot: {_fmt(snapshot_value)}", className="mb-1"),
                            html.P(f"Delta: {delta_text}", className="mb-0"),
                        ]
                    ),
                    className="shadow-sm",
                ),
                md=4,
                className="mb-3",
            )
        )
    return cards


def _comparison_figure(current_metrics: dict, snapshot_metrics: dict) -> go.Figure:
    keys = [
        ("Total Articles", "total_articles"),
        ("Scored Articles", "scored_articles"),
        ("Zero Scores", "zero_score_articles"),
        ("Unscorable", "unscorable_articles"),
        ("Score Coverage %", "score_coverage_ratio_percent"),
        ("Days Covered", "days_covered"),
    ]

    labels = [label for label, _ in keys]
    current_values = []
    snapshot_values = []
    for _, key in keys:
        current_value = current_metrics.get(key)
        snapshot_value = snapshot_metrics.get(key)
        current_values.append(float(current_value) if isinstance(current_value, (int, float)) else 0.0)
        snapshot_values.append(float(snapshot_value) if isinstance(snapshot_value, (int, float)) else 0.0)

    figure = go.Figure(
        data=[
            go.Bar(name="Current", x=labels, y=current_values, marker_color="#0d6efd"),
            go.Bar(name="Snapshot", x=labels, y=snapshot_values, marker_color="#6c757d"),
        ]
    )
    figure.update_layout(title="Current vs Snapshot Metrics", barmode="group", template="plotly_white")
    return figure


def _comparison_table(current_metrics: dict, snapshot_metrics: dict):
    header = html.Thead(html.Tr([html.Th("Metric"), html.Th("Current"), html.Th("Snapshot"), html.Th("Delta")]))
    rows = []
    metric_rows = [
        ("Generated At", "generated_at"),
        ("Total Articles", "total_articles"),
        ("Scored Articles", "scored_articles"),
        ("Zero Scores", "zero_score_articles"),
        ("Unscorable", "unscorable_articles"),
        ("Score Coverage %", "score_coverage_ratio_percent"),
        ("Source Count", "source_count"),
        ("Tag Count", "tag_count"),
        ("Days Covered", "days_covered"),
    ]

    for label, key in metric_rows:
        current_value = current_metrics.get(key)
        snapshot_value = snapshot_metrics.get(key)

        if isinstance(current_value, float):
            current_text = f"{current_value:.1f}"
        elif isinstance(current_value, int):
            current_text = str(current_value)
        elif current_value is None:
            current_text = "n/a"
        else:
            current_text = str(current_value)

        if isinstance(snapshot_value, float):
            snapshot_text = f"{snapshot_value:.1f}"
        elif isinstance(snapshot_value, int):
            snapshot_text = str(snapshot_value)
        elif snapshot_value is None:
            snapshot_text = "n/a"
        else:
            snapshot_text = str(snapshot_value)

        delta_text = "n/a"
        if isinstance(current_value, (int, float)) and isinstance(snapshot_value, (int, float)):
            delta = current_value - snapshot_value
            delta_text = f"{delta:+.1f}" if isinstance(delta, float) and not float(delta).is_integer() else f"{int(delta):+d}"

        rows.append(html.Tr([html.Td(label), html.Td(current_text), html.Td(snapshot_text), html.Td(delta_text)]))

    return dbc.Table([header, html.Tbody(rows)], bordered=True, striped=True, hover=True, responsive=True, size="sm")


layout = dbc.Container(
    [
        dcc.Interval(id="news-compare-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Snapshot Compare", className="mb-3"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Snapshot date (UTC)"),
                        dcc.Input(id="news-compare-snapshot-date", type="date", className="form-control"),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Run Compare", id="news-compare-refresh", color="primary"),
                    ],
                    md=2,
                ),
                dbc.Col(html.Div(id="news-compare-status"), md=7),
            ],
            className="mb-3",
        ),
        dbc.Row(id="news-compare-cards"),
        dbc.Row(
            [
                dbc.Col(html.Div(id="news-compare-table"), lg=7, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-compare-graph"), lg=5, className="mb-3"),
            ]
        ),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-compare-status", "children"),
    Output("news-compare-cards", "children"),
    Output("news-compare-table", "children"),
    Output("news-compare-graph", "figure"),
    Input("news-compare-load", "n_intervals"),
    Input("news-compare-refresh", "n_clicks"),
    State("news-compare-snapshot-date", "value"),
)
def load_snapshot_compare(_load_tick, _refresh_clicks, snapshot_date):
    force_refresh = ctx.triggered_id == "news-compare-refresh"

    if not snapshot_date:
        empty = _empty_figure("Select a snapshot date to compare")
        return (
            dbc.Alert("Select a snapshot date to compare current vs historical data.", color="warning", className="mb-0"),
            [],
            dbc.Alert("No comparison yet.", color="secondary", className="mb-0"),
            empty,
        )

    current_status, current_payload = api_get(
        "/api/news/stats",
        {"refresh": "true" if force_refresh else None},
    )
    snapshot_status, snapshot_payload = api_get(
        "/api/news/stats",
        {
            "snapshot_date": snapshot_date,
            "refresh": "true" if force_refresh else None,
        },
    )

    if current_status != 200 or snapshot_status != 200:
        current_error = current_payload.get("error") if isinstance(current_payload, dict) else "unknown"
        snapshot_error = snapshot_payload.get("error") if isinstance(snapshot_payload, dict) else "unknown"
        empty = _empty_figure("Comparison unavailable")
        return (
            dbc.Alert(
                f"Compare failed. current={current_status} ({current_error}) | "
                f"snapshot={snapshot_status} ({snapshot_error})",
                color="danger",
                className="mb-0",
            ),
            [],
            dbc.Alert("No comparison table available.", color="warning", className="mb-0"),
            empty,
        )

    current_metrics = _extract_metrics(current_payload)
    snapshot_metrics = _extract_metrics(snapshot_payload)

    status = dbc.Alert(
        (
            f"Comparison ready | snapshot_date={snapshot_date} | "
            f"current_generated={current_metrics.get('generated_at') or 'n/a'} | "
            f"snapshot_generated={snapshot_metrics.get('generated_at') or 'n/a'}"
        ),
        color="info",
        className="mb-0",
    )

    return (
        status,
        _metric_cards(current_metrics, snapshot_metrics),
        _comparison_table(current_metrics, snapshot_metrics),
        _comparison_figure(current_metrics, snapshot_metrics),
    )
