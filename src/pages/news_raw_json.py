from __future__ import annotations

import json

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, mode_label, snapshot_param


dash.register_page(
    __name__,
    path="/news/raw-json",
    name="News Raw JSON",
    title="NewsLens| News Raw JSON",
)


_ENDPOINT_OPTIONS = [
    {"label": "Digest", "value": "digest"},
    {"label": "Latest Digest Item", "value": "latest"},
    {"label": "Stats", "value": "stats"},
    {"label": "Freshness", "value": "freshness"},
]


def _endpoint_path(endpoint_key: str) -> str:
    if endpoint_key == "latest":
        return "/api/news/digest/latest"
    if endpoint_key == "stats":
        return "/api/news/stats"
    if endpoint_key == "freshness":
        return "/health/news-freshness"
    return "/api/news/digest"


layout = dbc.Container(
    [
        dcc.Interval(id="news-raw-load", interval=3000, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Raw JSON Explorer", className="mb-3"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Endpoint"),
                        dcc.Dropdown(id="news-raw-endpoint", options=_ENDPOINT_OPTIONS, value="digest", clearable=False),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Data mode"),
                        dcc.Dropdown(
                            id="news-raw-mode",
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
                        dcc.Input(id="news-raw-snapshot-date", type="date", className="form-control", disabled=True),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Date filter"),
                        dcc.Input(id="news-raw-date", type="text", placeholder="YYYY-MM-DD", className="form-control"),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Tag filter"),
                        dcc.Input(id="news-raw-tag", type="text", placeholder="OpenAI", className="form-control"),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Source filter"),
                        dcc.Input(id="news-raw-source", type="text", placeholder="NPR", className="form-control"),
                    ],
                    md=2,
                ),
            ],
            className="mb-2",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Limit"),
                        dcc.Input(id="news-raw-limit", type="number", min=1, max=500, step=1, value=20, className="form-control"),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        html.Div(
                            [
                                dbc.Button("Load", id="news-raw-apply", color="primary", className="me-2"),
                                dbc.Button("Refresh", id="news-raw-refresh", color="secondary"),
                            ]
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(html.Div(id="news-raw-status"), md=8),
            ],
            className="mb-3",
        ),
        dbc.Row(
            [
                dbc.Col(
                    html.Pre(id="news-raw-payload", className="dark-pre"),
                    width=12,
                )
            ]
        ),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-raw-status", "children"),
    Output("news-raw-payload", "children"),
    Input("news-raw-load", "n_intervals"),
    Input("news-raw-apply", "n_clicks"),
    Input("news-raw-refresh", "n_clicks"),
    State("news-raw-endpoint", "value"),
    State("news-raw-mode", "value"),
    State("news-raw-snapshot-date", "value"),
    State("news-raw-date", "value"),
    State("news-raw-tag", "value"),
    State("news-raw-source", "value"),
    State("news-raw-limit", "value"),
)
def load_news_raw_json(
    _load_tick,
    _apply_clicks,
    _refresh_clicks,
    endpoint_key,
    data_mode,
    snapshot_date,
    date_filter,
    tag_filter,
    source_filter,
    limit_value,
):
    force_refresh = ctx.triggered_id == "news-raw-refresh"
    path = _endpoint_path(endpoint_key or "digest")
    params = {
        "date": date_filter,
        "tag": tag_filter,
        "source": source_filter,
        "limit": limit_value if endpoint_key == "digest" else None,
        "snapshot_date": snapshot_param(data_mode, snapshot_date),
        "refresh": "true" if force_refresh else None,
    }

    status_code, payload = api_get(path, params)
    payload_text = json.dumps(payload, indent=2, default=str)

    meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
    if isinstance(meta, dict) and meta:
        mode = mode_label(meta)
        generated_at = meta.get("generated_at")
    else:
        mode = data_mode or "current"
        generated_at = None

    status_color = "info" if status_code == 200 else "warning"
    return (
        build_status_alert(
            meta,
            leading_parts=[f"Endpoint: {path}", f"HTTP: {status_code}", f"Mode: {mode}"],
            color=status_color,
            class_name="mb-0",
        ),
        payload_text,
    )


@callback(
    Output("news-raw-snapshot-date", "disabled"),
    Input("news-raw-mode", "value"),
)
def toggle_raw_snapshot_input(data_mode):
    return data_mode != "snapshot"
