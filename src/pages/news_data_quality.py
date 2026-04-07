from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/data-quality",
    name="News Data Quality",
    title="NewsLens | News Data Quality",
)


def _is_populated(value) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, dict):
        return len(value) > 0
    return value is not None


def _field_coverage_rows(records: list[dict]) -> list[dict]:
    fields = [
        ("Title", lambda row: row.get("title")),
        ("Link", lambda row: row.get("link")),
        ("Published At", lambda row: row.get("published_at")),
        ("Source Name", lambda row: (row.get("source") or {}).get("name") if isinstance(row.get("source"), dict) else None),
        ("AI Summary", lambda row: row.get("ai_summary")),
        ("Summary", lambda row: row.get("summary")),
        ("Tags", lambda row: row.get("tags")),
        ("Score Percent", lambda row: (row.get("score") or {}).get("percent") if isinstance(row.get("score"), dict) else None),
        (
            "Lens Scores",
            lambda row: (row.get("score") or {}).get("lens_scores") if isinstance(row.get("score"), dict) else None,
        ),
    ]

    total = len(records)
    rows: list[dict] = []
    for label, getter in fields:
        present = 0
        for record in records:
            if _is_populated(getter(record)):
                present += 1
        missing = max(total - present, 0)
        coverage_percent = (present / total * 100.0) if total else 0.0
        rows.append(
            {
                "field": label,
                "present": present,
                "missing": missing,
                "coverage_percent": coverage_percent,
            }
        )
    return rows


def _quality_summary(records: list[dict]) -> dict:
    total = len(records)
    tag_counts = [len(record.get("tags", [])) for record in records if isinstance(record.get("tags"), list)]
    average_tags = (sum(tag_counts) / len(tag_counts)) if tag_counts else 0.0
    missing_ai_summary = sum(1 for record in records if not _is_populated(record.get("ai_summary")))
    missing_published = sum(1 for record in records if not _is_populated(record.get("published_at")))
    missing_source = sum(
        1
        for record in records
        if not _is_populated((record.get("source") or {}).get("name") if isinstance(record.get("source"), dict) else None)
    )
    scored = sum(
        1
        for record in records
        if isinstance(record.get("score"), dict) and isinstance(record["score"].get("percent"), (int, float))
    )

    return {
        "total": total,
        "scored": scored,
        "missing_ai_summary": missing_ai_summary,
        "missing_published": missing_published,
        "missing_source": missing_source,
        "average_tags": average_tags,
    }


def _summary_cards(meta: dict, stats_derived: dict, quality: dict):
    cards = [
        ("Input Articles", meta.get("input_articles_count", "n/a")),
        ("Excluded Unscraped", meta.get("excluded_unscraped_articles", "n/a")),
        ("Included (Digest)", quality.get("total", "n/a")),
        ("Scored (Digest)", quality.get("scored", "n/a")),
        ("High Scoring", stats_derived.get("high_scoring_articles", "n/a")),
        ("Avg Tags / Article", f"{quality.get('average_tags', 0.0):.2f}"),
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
        dbc.Row(
            [
                dbc.Col(
                    html.P(
                        "Notebook bootstrap parity page for quick data diagnostics and field completeness checks.",
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
                        dbc.Label("Digest limit"),
                        dcc.Input(id="news-quality-limit", type="number", min=25, max=500, step=25, value=500, className="form-control"),
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
    State("news-quality-limit", "value"),
)
def load_news_data_quality(_load_tick, _refresh_clicks, data_mode, snapshot_date, limit_value):
    force_refresh = ctx.triggered_id == "news-quality-refresh"
    limit = int(limit_value) if isinstance(limit_value, (int, float)) else 500
    limit = max(25, min(limit, 500))
    snapshot = snapshot_param(data_mode, snapshot_date)

    digest_status, digest_payload = api_get(
        "/api/news/digest",
        {
            "snapshot_date": snapshot,
            "limit": limit,
            "refresh": "true" if force_refresh else None,
        },
    )
    stats_status, stats_payload = api_get(
        "/api/news/stats",
        {
            "snapshot_date": snapshot,
            "refresh": "true" if force_refresh else None,
        },
    )

    if digest_status != 200:
        error = digest_payload.get("error", "Unknown error")
        alert = dbc.Alert(f"Digest error ({digest_status}): {error}", color="danger")
        return alert, [], alert, alert

    records = digest_payload.get("data", [])
    records_list = records if isinstance(records, list) else []
    meta = digest_payload.get("meta", {}) if isinstance(digest_payload.get("meta"), dict) else {}

    stats_data = stats_payload.get("data", {}) if isinstance(stats_payload, dict) else {}
    derived = stats_data.get("derived", {}) if isinstance(stats_data, dict) else {}
    derived_stats = derived if isinstance(derived, dict) else {}

    coverage_rows = _field_coverage_rows(records_list)
    quality = _quality_summary(records_list)

    return (
        build_status_alert(
            meta,
            leading_parts=[
                f"Digest HTTP: {digest_status}",
                f"Stats HTTP: {stats_status}",
                f"Digest limit: {limit}",
            ],
            color="info" if stats_status == 200 else "warning",
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
