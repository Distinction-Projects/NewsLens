from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_news_intro, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/workflow-status",
    name="News Workflow Status",
    title="NewsLens | News Workflow Status",
)


def _badge_for_status(status: str):
    if status == "pass":
        return dbc.Badge("PASS", color="success", className="ms-2")
    if status == "warn":
        return dbc.Badge("WARN", color="warning", className="ms-2")
    return dbc.Badge("FAIL", color="danger", className="ms-2")


def _check_row(label: str, status: str, details: str):
    return dbc.ListGroupItem(
        [
            html.Div([html.Strong(label), _badge_for_status(status)]),
            html.Div(details, className="small text-muted"),
        ]
    )


def _summary_cards(
    input_articles: int | None,
    excluded_unscraped: int | None,
    included_articles: int | None,
    scored_articles: int | None,
    zero_score_articles: int | None,
    unscorable_articles: int | None,
    score_coverage_ratio: float | None,
):
    score_coverage_text = (
        f"{score_coverage_ratio * 100:.1f}%"
        if isinstance(score_coverage_ratio, (int, float))
        else "n/a"
    )
    cards = [
        ("Input Articles", input_articles if isinstance(input_articles, int) else "n/a", "primary"),
        ("Excluded (Scrape Errors)", excluded_unscraped if isinstance(excluded_unscraped, int) else "n/a", "danger"),
        ("Included Articles", included_articles if isinstance(included_articles, int) else "n/a", "info"),
        ("Scored Articles", scored_articles if isinstance(scored_articles, int) else "n/a", "success"),
        ("Zero Scores", zero_score_articles if isinstance(zero_score_articles, int) else "n/a", "secondary"),
        ("Unscorable", unscorable_articles if isinstance(unscorable_articles, int) else "n/a", "dark"),
        ("Score Coverage", score_coverage_text, "warning"),
    ]
    return [
        dbc.Col(
            dbc.Card(
                dbc.CardBody([html.P(label, className="text-muted mb-1"), html.H4(str(value), className="mb-0")]),
                className="shadow-sm",
                color=color,
            ),
            md=2,
            className="mb-3",
        )
        for label, value, color in cards
    ]


def _latest_card(record: dict | None):
    if not isinstance(record, dict):
        return dbc.Alert("Latest article unavailable for current filters.", color="warning", className="mb-0")

    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    source_name = source.get("name") or source.get("id") or "Unknown source"
    published = record.get("published_at") or record.get("published") or "Unknown date"
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(record.get("title") or "Untitled", className="mb-2"),
                html.P(f"Source: {source_name}", className="mb-1"),
                html.P(f"Published (UTC): {published}", className="mb-2"),
                html.P(record.get("ai_summary") or record.get("summary") or "No summary available.", className="mb-2"),
                dbc.Button("Open Article", href=record.get("link"), target="_blank", color="secondary", size="sm")
                if record.get("link")
                else html.Small("No link provided.", className="text-muted"),
            ]
        ),
        className="shadow-sm",
    )


layout = dbc.Container(
    [
        dcc.Interval(id="news-workflow-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Workflow Status", className="mb-3"), width=12)]),
        build_news_intro(
            "Monitor freshness, scrape/scoring health, and current pipeline status."
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Data mode"),
                        dcc.Dropdown(
                            id="news-workflow-mode",
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
                        dcc.Input(
                            id="news-workflow-snapshot-date",
                            type="date",
                            className="form-control",
                            disabled=True,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh Checks", id="news-workflow-refresh", color="secondary"),
                    ],
                    md=2,
                ),
                dbc.Col(html.Div(id="news-workflow-status"), md=6),
            ],
            className="mb-2",
        ),
        dbc.Row(id="news-workflow-cards"),
        dbc.Row(
            [
                dbc.Col(html.Div(id="news-workflow-checks"), lg=7, className="mb-3"),
                dbc.Col(html.Div(id="news-workflow-latest"), lg=5, className="mb-3"),
            ]
        ),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-workflow-status", "children"),
    Output("news-workflow-cards", "children"),
    Output("news-workflow-checks", "children"),
    Output("news-workflow-latest", "children"),
    Input("news-workflow-load", "n_intervals"),
    Input("news-workflow-refresh", "n_clicks"),
    State("news-workflow-mode", "value"),
    State("news-workflow-snapshot-date", "value"),
)
def load_workflow_status(_load_tick, _refresh_clicks, data_mode, snapshot_date):
    force_refresh = ctx.triggered_id == "news-workflow-refresh"
    snapshot_date_value = snapshot_param(data_mode, snapshot_date)
    common_params = {
        "snapshot_date": snapshot_date_value,
        "refresh": "true" if force_refresh else None,
    }

    digest_status, digest_payload = api_get("/api/news/digest", common_params)
    latest_status, latest_payload = api_get("/api/news/digest/latest", common_params)
    stats_status, stats_payload = api_get("/api/news/stats", common_params)
    freshness_status, freshness_payload = api_get(
        "/health/news-freshness",
        {"refresh": "true" if force_refresh and data_mode == "current" else None},
    )

    digest_meta = digest_payload.get("meta") if isinstance(digest_payload, dict) and isinstance(digest_payload.get("meta"), dict) else {}
    stats_meta = stats_payload.get("meta") if isinstance(stats_payload, dict) and isinstance(stats_payload.get("meta"), dict) else {}
    stats_data = stats_payload.get("data") if isinstance(stats_payload, dict) and isinstance(stats_payload.get("data"), dict) else {}
    derived = stats_data.get("derived") if isinstance(stats_data.get("derived"), dict) else {}

    input_articles = digest_meta.get("input_articles_count")
    excluded_unscraped = digest_meta.get("excluded_unscraped_articles")
    included_articles = derived.get("total_articles")
    scored_articles = derived.get("scored_articles")
    zero_score_articles = derived.get("zero_score_articles")
    unscorable_articles = derived.get("unscorable_articles")
    score_coverage_ratio = derived.get("score_coverage_ratio")

    ingest_ok = digest_status == 200
    scrape_filter_ok = (
        isinstance(input_articles, int)
        and isinstance(excluded_unscraped, int)
        and isinstance(included_articles, int)
        and input_articles >= included_articles
        and excluded_unscraped >= 0
    )
    scoring_ok = stats_status == 200 and isinstance(scored_articles, int) and scored_articles > 0
    unscorable_ok = stats_status == 200 and isinstance(unscorable_articles, int) and unscorable_articles == 0
    precompute_ok = stats_status == 200 and bool(stats_meta.get("schema_version"))

    if data_mode == "snapshot":
        freshness_label = "Snapshot mode does not use freshness health gate."
        freshness_state = "warn"
    else:
        freshness_state = "pass" if freshness_status == 200 else "fail"
        freshness_label = (
            f"current freshness endpoint -> HTTP {freshness_status}; "
            f"is_fresh={freshness_payload.get('is_fresh')}"
        )

    checks = dbc.Card(
        dbc.CardBody(
            [
                html.H5("Pipeline Stage Checks", className="mb-3"),
                dbc.ListGroup(
                    [
                        _check_row(
                            "Ingest + digest endpoint",
                            "pass" if ingest_ok else "fail",
                            f"/api/news/digest -> HTTP {digest_status}",
                        ),
                        _check_row(
                            "Scrape filtering in effect",
                            "pass" if scrape_filter_ok else "fail",
                            (
                                f"input={input_articles}, excluded_unscraped={excluded_unscraped}, "
                                f"included={included_articles}"
                            ),
                        ),
                        _check_row(
                            "Rubric scoring present",
                            "pass" if scoring_ok else "fail",
                            (
                                f"scored_articles={scored_articles}, "
                                f"zero_scores={zero_score_articles}, unscorable={unscorable_articles}"
                            ),
                        ),
                        _check_row(
                            "Unscorable article gate",
                            "pass" if unscorable_ok else "warn",
                            "Warn when included articles are missing usable score outputs.",
                        ),
                        _check_row(
                            "Precomputed contract present",
                            "pass" if precompute_ok else "fail",
                            f"schema_version={stats_meta.get('schema_version')}",
                        ),
                        _check_row(
                            "Freshness gate",
                            freshness_state,
                            freshness_label,
                        ),
                    ]
                ),
            ]
        ),
        className="shadow-sm",
    )

    mode_meta = digest_meta if digest_meta else stats_meta
    alert_color = "info" if ingest_ok and stats_status == 200 else "warning"
    latest_record = latest_payload.get("data") if latest_status == 200 and isinstance(latest_payload, dict) else None

    return (
        build_status_alert(
            mode_meta,
            leading_parts=[
                f"Digest HTTP: {digest_status}",
                f"Stats HTTP: {stats_status}",
                f"Latest HTTP: {latest_status}",
            ],
            color=alert_color,
            class_name="mb-0",
        ),
        _summary_cards(
            input_articles,
            excluded_unscraped,
            included_articles,
            scored_articles,
            zero_score_articles,
            unscorable_articles,
            score_coverage_ratio,
        ),
        checks,
        _latest_card(latest_record),
    )


@callback(
    Output("news-workflow-snapshot-date", "disabled"),
    Input("news-workflow-mode", "value"),
)
def toggle_workflow_snapshot_input(data_mode):
    return data_mode != "snapshot"
