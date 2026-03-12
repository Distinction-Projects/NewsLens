from __future__ import annotations

from urllib.parse import urlencode

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
