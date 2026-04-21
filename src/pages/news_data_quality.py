from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_news_intro, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/data-quality",
    name="News Data Quality",
    title="NewsLens | News Data Quality",
)


def _data_quality_from_stats(derived: dict) -> dict:
    quality = derived.get("data_quality") if isinstance(derived, dict) else None
    quality_obj = quality if isinstance(quality, dict) else {}
    summary = quality_obj.get("summary") if isinstance(quality_obj.get("summary"), dict) else {}
    field_coverage = quality_obj.get("field_coverage") if isinstance(quality_obj.get("field_coverage"), list) else []
    return {
        "summary": summary,
        "field_coverage": field_coverage,
    }


def _summary_cards(meta: dict, stats_derived: dict, quality: dict):
    score_coverage_ratio = stats_derived.get("score_coverage_ratio")
    score_coverage_text = (
        f"{score_coverage_ratio * 100:.1f}%"
        if isinstance(score_coverage_ratio, (int, float))
        else "n/a"
    )
    zero_score_articles = stats_derived.get("zero_score_articles", "n/a")
    unscorable_articles = stats_derived.get("unscorable_articles", "n/a")
    cards = [
        ("Input Articles", meta.get("input_articles_count", "n/a")),
        ("Excluded Unscraped", meta.get("excluded_unscraped_articles", "n/a")),
        ("Included (Digest)", quality.get("total", "n/a")),
        ("Scored (Digest)", quality.get("scored", "n/a")),
        ("Zero Scores", zero_score_articles if isinstance(zero_score_articles, int) else "n/a"),
        ("Unscorable", unscorable_articles if isinstance(unscorable_articles, int) else "n/a"),
        ("Score Coverage", score_coverage_text),
        ("Avg Tags / Article", f"{quality.get('average_tags', 0.0):.2f}"),
    ]
    return [
        dbc.Col(
            dbc.Card(
                dbc.CardBody([html.P(label, className="text-muted mb-1"), html.H4(str(value), className="mb-0")]),
                className="shadow-sm",
            ),
            md=3,
            lg=3,
            className="mb-3",
        )
        for label, value in cards
    ]


def _coverage_table(rows: list[dict]):
    if not rows:
        return dbc.Alert("No records available for coverage calculations.", color="warning", className="mb-0")

    body = [
        html.Tr(
            [
                html.Td(row["field"]),
                html.Td(str(row["present"])),
                html.Td(str(row["missing"])),
                html.Td(f"{row['coverage_percent']:.1f}%"),
            ]
        )
        for row in rows
    ]
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5("Field Coverage", className="card-title"),
                dbc.Table(
                    [
                        html.Thead(html.Tr([html.Th("Field"), html.Th("Present"), html.Th("Missing"), html.Th("Coverage")])),
                        html.Tbody(body),
                    ],
                    bordered=True,
                    striped=True,
                    hover=True,
                    responsive=True,
                    size="sm",
                    class_name="mb-0",
                ),
            ]
        ),
        className="shadow-sm",
    )


def _issues_list(quality: dict):
    issues = [
        f"Missing AI summary: {quality.get('missing_ai_summary', 0)}",
        f"Missing published_at: {quality.get('missing_published', 0)}",
        f"Missing source name: {quality.get('missing_source', 0)}",
    ]
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5("Data Quality Checks", className="card-title"),
                dbc.ListGroup([dbc.ListGroupItem(issue) for issue in issues]),
            ]
        ),
        className="shadow-sm",
    )


layout = dbc.Container(
    [
        dcc.Interval(id="news-quality-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Data Quality", className="mb-2"), width=12)]),
        build_news_intro(
            "Audit missingness, unscorable records, and data quality diagnostics."
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Data mode"),
                        dcc.Dropdown(
                            id="news-quality-mode",
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
                        dcc.Input(id="news-quality-snapshot-date", type="date", className="form-control", disabled=True),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-quality-refresh", color="secondary"),
                    ],
                    md=2,
                ),
            ],
            className="mb-3",
        ),
        dbc.Row([dbc.Col(html.Div(id="news-quality-status"), width=12)]),
        dbc.Row(id="news-quality-cards"),
        dbc.Row(
            [
                dbc.Col(html.Div(id="news-quality-coverage"), lg=8, className="mb-3"),
                dbc.Col(html.Div(id="news-quality-issues"), lg=4, className="mb-3"),
            ]
        ),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-quality-status", "children"),
    Output("news-quality-cards", "children"),
    Output("news-quality-coverage", "children"),
    Output("news-quality-issues", "children"),
    Input("news-quality-load", "n_intervals"),
    Input("news-quality-refresh", "n_clicks"),
    State("news-quality-mode", "value"),
    State("news-quality-snapshot-date", "value"),
)
def load_news_data_quality(_load_tick, _refresh_clicks, data_mode, snapshot_date):
    force_refresh = ctx.triggered_id == "news-quality-refresh"
    snapshot = snapshot_param(data_mode, snapshot_date)

    stats_status, stats_payload = api_get(
        "/api/news/stats",
        {
            "snapshot_date": snapshot,
            "refresh": "true" if force_refresh else None,
        },
    )
    if stats_status != 200:
        error = stats_payload.get("error", "Unknown error")
        alert = dbc.Alert(f"Stats error ({stats_status}): {error}", color="danger")
        return alert, [], alert, alert

    stats_data = stats_payload.get("data", {}) if isinstance(stats_payload, dict) else {}
    meta = stats_payload.get("meta", {}) if isinstance(stats_payload.get("meta"), dict) else {}
    derived = stats_data.get("derived", {}) if isinstance(stats_data, dict) else {}
    derived_stats = derived if isinstance(derived, dict) else {}
    quality_payload = _data_quality_from_stats(derived_stats)
    coverage_rows = quality_payload.get("field_coverage", [])
    quality = quality_payload.get("summary", {})

    return (
        build_status_alert(
            meta,
            leading_parts=[
                f"Stats HTTP: {stats_status}",
                f"Included articles: {quality.get('total', derived_stats.get('total_articles', 0))}",
            ],
            color="info",
        ),
        _summary_cards(meta, derived_stats, quality),
        _coverage_table(coverage_rows),
        _issues_list(quality),
    )


@callback(
    Output("news-quality-snapshot-date", "disabled"),
    Input("news-quality-mode", "value"),
)
def toggle_data_quality_snapshot_input(data_mode):
    return data_mode != "snapshot"
