import json
from collections import defaultdict
from urllib.parse import urlencode

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, ctx, dcc, html
from flask import current_app


dash.register_page(
    __name__,
    path="/news/scraped",
    name="News Scraped",
    title="Sentiment Analyzer | News Scraped",
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


def _source_name(record: dict) -> str:
    source = record.get("source")
    if isinstance(source, dict):
        return source.get("name") or source.get("id") or "Unknown source"
    return "Unknown source"


def _has_scraped_payload(record: dict) -> bool:
    scraped = record.get("scraped")
    return isinstance(scraped, dict) and bool(scraped)


def _article_block(record: dict) -> dbc.Card:
    scraped = record.get("scraped")
    raw_text = json.dumps(scraped, indent=2, default=str) if isinstance(scraped, dict) else "No scraped payload."
    published = record.get("published_at") or record.get("published") or "Unknown date"
    score = record.get("score") if isinstance(record.get("score"), dict) else {}
    score_percent = score.get("percent")
    score_text = f"{score_percent:.1f}%" if isinstance(score_percent, (int, float)) else "n/a"

    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(
                    [
                        html.Strong(record.get("title") or "Untitled"),
                        html.Span(f"  [{record.get('id') or 'no-id'}]", className="text-muted small ms-2"),
                    ],
                    className="mb-1",
                ),
                html.Div(
                    [
                        html.Span(f"Published: {published}", className="me-3"),
                        html.Span(f"Score: {score_text}", className="me-3"),
                        html.Span(f"Has scraped: {'yes' if _has_scraped_payload(record) else 'no'}"),
                    ],
                    className="small text-muted mb-2",
                ),
                html.Div(
                    dbc.Button("Open article", href=record.get("link"), target="_blank", color="secondary", size="sm")
                    if record.get("link")
                    else html.Small("No link", className="text-muted"),
                    className="mb-2",
                ),
                html.Pre(
                    raw_text,
                    className="dark-pre",
                ),
            ]
        ),
        className="mb-3 shadow-sm",
    )


def _render_by_source(records: list[dict], only_scraped: bool) -> list:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        if only_scraped and not _has_scraped_payload(record):
            continue
        grouped[_source_name(record)].append(record)

    if not grouped:
        return [dbc.Alert("No records match the current filters.", color="warning", className="mb-0")]

    accordion_items = []
    for source_name in sorted(grouped.keys()):
        source_records = grouped[source_name]
        label = f"{source_name} ({len(source_records)} article{'s' if len(source_records) != 1 else ''})"
        accordion_items.append(
            dbc.AccordionItem(
                [html.Div([_article_block(record) for record in source_records])],
                title=label,
            )
        )

    return [dbc.Accordion(accordion_items, start_collapsed=True, flush=False, always_open=False)]


layout = dbc.Container(
    [
        dcc.Interval(id="news-scraped-load", interval=3000, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("Raw Scraped Article Data", className="mb-3"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Data mode"),
                        dcc.Dropdown(
                            id="news-scraped-data-mode",
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
                            id="news-scraped-snapshot-date",
                            type="date",
                            className="form-control",
                            disabled=True,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Source filter"),
                        dcc.Input(id="news-scraped-source", type="text", placeholder="Fox, PBS, NPR...", className="form-control"),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        dbc.Label("Limit"),
                        dcc.Input(id="news-scraped-limit", type="number", min=1, max=500, step=1, value=100, className="form-control"),
                    ],
                    md=1,
                ),
                dbc.Col(
                    [
                        dbc.Label("Only show records with scraped payload"),
                        dbc.Checklist(
                            id="news-scraped-only",
                            options=[{"label": "enabled", "value": "yes"}],
                            value=["yes"],
                            switch=True,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        html.Div(
                            [
                                dbc.Button("Apply", id="news-scraped-apply", color="primary", className="me-2"),
                                dbc.Button("Refresh", id="news-scraped-refresh", color="secondary"),
                            ]
                        ),
                    ],
                    md=2,
                ),
            ],
            className="mb-3",
        ),
        dbc.Row([dbc.Col(html.Div(id="news-scraped-status"), width=12)]),
        dbc.Row([dbc.Col(html.Div(id="news-scraped-content"), width=12)]),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-scraped-status", "children"),
    Output("news-scraped-content", "children"),
    Input("news-scraped-load", "n_intervals"),
    Input("news-scraped-apply", "n_clicks"),
    Input("news-scraped-refresh", "n_clicks"),
    State("news-scraped-source", "value"),
    State("news-scraped-limit", "value"),
    State("news-scraped-only", "value"),
    State("news-scraped-data-mode", "value"),
    State("news-scraped-snapshot-date", "value"),
)
def load_scraped_news(
    _load_tick,
    _apply_clicks,
    _refresh_clicks,
    source_filter,
    limit_value,
    only_scraped_values,
    data_mode,
    snapshot_date,
):
    force_refresh = ctx.triggered_id == "news-scraped-refresh"
    only_scraped = isinstance(only_scraped_values, list) and "yes" in only_scraped_values
    snapshot_date_param = snapshot_date if data_mode == "snapshot" else None

    params = {
        "source": source_filter,
        "limit": limit_value or 100,
        "snapshot_date": snapshot_date_param,
        "refresh": "true" if force_refresh else None,
    }
    status_code, payload = _api_get("/api/news/digest", params)

    if status_code != 200:
        error = payload.get("error") or json.dumps(payload)
        return (
            dbc.Alert(f"Failed to load digest ({status_code}): {error}", color="danger", className="mb-3"),
            [dbc.Alert("No scraped data available.", color="warning")],
        )

    meta = payload.get("meta", {})
    records = payload.get("data", [])
    source_mode = meta.get("source_mode") or "current"
    snapshot_active = meta.get("snapshot_date")
    mode_label = source_mode if source_mode != "snapshot" else f"snapshot ({snapshot_active or 'missing-date'})"
    status_line = (
        f"Mode: {mode_label} | "
        f"Records loaded: {len(records)} | "
        f"Generated at: {meta.get('generated_at')} | "
        f"Cache: {'hit' if meta.get('from_cache') else 'miss'}"
    )
    if meta.get("using_last_good"):
        status_line += " | using last-good fallback"
    if only_scraped:
        status_line += " | filtered to records with scraped payload"

    return dbc.Alert(status_line, color="info", className="mb-3"), _render_by_source(records, only_scraped=only_scraped)


@callback(
    Output("news-scraped-snapshot-date", "disabled"),
    Input("news-scraped-data-mode", "value"),
)
def toggle_scraped_snapshot_input(data_mode):
    return data_mode != "snapshot"
