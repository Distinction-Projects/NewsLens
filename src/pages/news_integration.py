import json
from urllib.parse import urlencode

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, ctx, dcc, html
from flask import current_app


dash.register_page(
    __name__,
    path="/news/integration",
    name="News Integration",
    title="NewsLens | News Integration",
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


def _status_badge(ok: bool, ok_label: str = "PASS", bad_label: str = "FAIL") -> dbc.Badge:
    return dbc.Badge(ok_label if ok else bad_label, color="success" if ok else "danger", className="ms-2")


def _status_row(label: str, ok: bool, details: str) -> dbc.ListGroupItem:
    return dbc.ListGroupItem(
        [
            html.Div([html.Strong(label), _status_badge(ok)]),
            html.Div(details, className="me-3"),
        ]
    )


layout = dbc.Container(
    [
        dcc.Interval(id="news-integration-load", interval=3000, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Integration Monitor", className="mb-2"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    html.P(
                        "Connectivity and payload checks for RSS contract ingestion in this app runtime.",
                        className="text-muted mb-3",
                    ),
                    width=12,
                )
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button("Refresh Checks", id="news-integration-refresh", color="primary", className="mb-3"),
                    width=12,
                )
            ]
        ),
        dbc.Row([dbc.Col(html.Div(id="news-integration-banner"), width=12)]),
        dbc.Row(
            [
                dbc.Col(html.Div(id="news-integration-summary"), lg=5, className="mb-3"),
                dbc.Col(html.Div(id="news-integration-checks"), lg=7, className="mb-3"),
            ]
        ),
        dbc.Row([dbc.Col(html.Pre(id="news-integration-debug", className="small dark-pre"), width=12)]),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-integration-banner", "children"),
    Output("news-integration-summary", "children"),
    Output("news-integration-checks", "children"),
    Output("news-integration-debug", "children"),
    Input("news-integration-load", "n_intervals"),
    Input("news-integration-refresh", "n_clicks"),
)
def load_news_integration(_load_tick, _refresh_clicks):
    force_refresh = ctx.triggered_id == "news-integration-refresh"
    refresh_param = {"refresh": "true" if force_refresh else None}

    digest_code, digest_payload = _api_get("/api/news/digest", {"limit": 5, **refresh_param})
    latest_code, latest_payload = _api_get("/api/news/digest/latest", refresh_param)
    stats_code, stats_payload = _api_get("/api/news/stats", refresh_param)
    freshness_code, freshness_payload = _api_get("/health/news-freshness", refresh_param)

    digest_ok = digest_code == 200
    stats_ok = stats_code == 200
    freshness_reachable = freshness_code in (200, 503)

    digest_meta = digest_payload.get("meta", {}) if isinstance(digest_payload, dict) else {}
    generated_at = digest_meta.get("generated_at")
    has_generated_at = isinstance(generated_at, str) and bool(generated_at.strip())

    digest_items = digest_payload.get("data", []) if isinstance(digest_payload, dict) else []
    has_articles = isinstance(digest_items, list) and len(digest_items) > 0

    latest_item = latest_payload.get("data") if latest_code == 200 and isinstance(latest_payload, dict) else None
    latest_title = latest_item.get("title") if isinstance(latest_item, dict) else None
    freshness_is_fresh = bool(freshness_payload.get("is_fresh")) if isinstance(freshness_payload, dict) else False

    integration_ok = digest_ok and stats_ok and freshness_reachable and has_generated_at
    stale_warning = freshness_reachable and not freshness_is_fresh

    if integration_ok and not stale_warning:
        banner = dbc.Alert("Integration checks passing. Data is fresh.", color="success", className="mb-3")
    elif integration_ok and stale_warning:
        banner = dbc.Alert(
            "Integration checks passing, but freshness is stale (expected if upstream has not published recently).",
            color="warning",
            className="mb-3",
        )
    else:
        banner = dbc.Alert("Integration check failure. Review endpoint statuses below.", color="danger", className="mb-3")

    summary = dbc.Card(
        dbc.CardBody(
            [
                html.H5("Runtime Summary", className="mb-3"),
                html.P(f"Generated at: {generated_at or 'missing'}", className="mb-1"),
                html.P(f"Digest returned: {len(digest_items) if isinstance(digest_items, list) else 0} item(s)", className="mb-1"),
                html.P(f"Latest title: {latest_title or 'unavailable'}", className="mb-1"),
                html.P(f"Freshness status: {'fresh' if freshness_is_fresh else 'stale'}", className="mb-0"),
            ]
        ),
        className="shadow-sm",
    )

    checks = dbc.Card(
        dbc.CardBody(
            [
                html.H5("Check List", className="mb-3"),
                dbc.ListGroup(
                    [
                        _status_row(
                            "Digest endpoint reachable",
                            digest_ok,
                            f"/api/news/digest -> HTTP {digest_code}",
                        ),
                        _status_row(
                            "Stats endpoint reachable",
                            stats_ok,
                            f"/api/news/stats -> HTTP {stats_code}",
                        ),
                        _status_row(
                            "Freshness endpoint reachable",
                            freshness_reachable,
                            f"/health/news-freshness -> HTTP {freshness_code}",
                        ),
                        _status_row(
                            "Payload includes generated_at",
                            has_generated_at,
                            f"generated_at={generated_at}",
                        ),
                        _status_row(
                            "Payload has articles",
                            has_articles,
                            f"items={len(digest_items) if isinstance(digest_items, list) else 0}",
                        ),
                    ]
                ),
            ]
        ),
        className="shadow-sm",
    )

    debug_payload = {
        "digest_status_code": digest_code,
        "latest_status_code": latest_code,
        "stats_status_code": stats_code,
        "freshness_status_code": freshness_code,
        "digest_status": digest_payload.get("status"),
        "latest_status": latest_payload.get("status"),
        "stats_status": stats_payload.get("status"),
        "freshness_status": freshness_payload.get("status"),
        "from_cache": digest_meta.get("from_cache"),
        "using_last_good": digest_meta.get("using_last_good"),
        "fetch_error": digest_meta.get("fetch_error"),
        "freshness_reason": freshness_payload.get("reason"),
    }
    debug_text = json.dumps(debug_payload, indent=2, default=str)

    return banner, summary, checks, debug_text
