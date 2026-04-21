from __future__ import annotations

from urllib.parse import urlencode

import dash_bootstrap_components as dbc
from dash import html
from flask import current_app


def api_get(path: str, params: dict[str, str | int | None]) -> tuple[int, dict]:
    filtered = {key: value for key, value in params.items() if value not in (None, "", [])}
    query = urlencode(filtered, doseq=True)
    target = f"{path}?{query}" if query else path
    with current_app.test_client() as client:
        response = client.get(target)
    parsed = response.get_json(silent=True)
    if isinstance(parsed, dict):
        return response.status_code, parsed
    return response.status_code, {"status": "error", "error": response.get_data(as_text=True)}


def snapshot_param(data_mode: str | None, snapshot_date: str | None) -> str | None:
    if data_mode == "snapshot":
        return snapshot_date
    return None


def mode_label(meta: dict) -> str:
    source_mode = meta.get("source_mode") if isinstance(meta, dict) else None
    if source_mode != "snapshot":
        return "current"
    snapshot_date = meta.get("snapshot_date") if isinstance(meta, dict) else None
    return f"snapshot ({snapshot_date or 'missing-date'})"


def build_news_intro(summary_text: str) -> dbc.Row:
    text = str(summary_text or "").strip()
    return dbc.Row(
        [
            dbc.Col(
                dbc.Accordion(
                    [
                        dbc.AccordionItem(
                            html.P(text, className="mb-0"),
                            title="What this page does",
                        )
                    ],
                    start_collapsed=True,
                    flush=True,
                    className="news-page-intro",
                ),
                width=12,
            )
        ],
        className="mb-3",
    )


def build_status_alert(
    meta: dict | None,
    *,
    leading_parts: list[str] | None = None,
    trailing_parts: list[str] | None = None,
    color: str = "info",
    class_name: str = "mb-3",
):
    meta = meta if isinstance(meta, dict) else {}
    details: list[str] = []
    details.extend(leading_parts or [])
    details.append(f"Mode: {mode_label(meta)}")
    details.append(f"Cache: {'hit' if meta.get('from_cache') else 'miss'}")
    if meta.get("using_last_good"):
        details.append("using last-good fallback")
    details.extend(trailing_parts or [])

    return dbc.Alert(
        [
            html.Div([html.Strong("Last updated: "), meta.get("generated_at") or "n/a"], className="mb-1"),
            html.Div(" | ".join(details), className="small mb-0"),
        ],
        color=color,
        className=f"news-status-alert {class_name}",
    )
