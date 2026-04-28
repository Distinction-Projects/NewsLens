from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_NEWS_STATS_SNAPSHOT_PATH = "data/processed/news_analytics_snapshot.json"


class PrecomputedStatsError(RuntimeError):
    pass


def stats_backend_mode() -> str:
    mode = (os.getenv("NEWS_STATS_BACKEND") or "dynamic").strip().lower()
    if mode in {"precomputed", "snapshot"}:
        return "precomputed"
    return "dynamic"


def stats_snapshot_path() -> Path:
    configured = (os.getenv("NEWS_STATS_SNAPSHOT_PATH") or DEFAULT_NEWS_STATS_SNAPSHOT_PATH).strip()
    return Path(configured or DEFAULT_NEWS_STATS_SNAPSHOT_PATH)


def _validate_stats_envelope(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise PrecomputedStatsError("Precomputed stats snapshot must be a JSON object.")
    if payload.get("status") != "ok":
        raise PrecomputedStatsError("Precomputed stats snapshot must have status=ok.")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise PrecomputedStatsError("Precomputed stats snapshot is missing data object.")
    derived = data.get("derived")
    if not isinstance(derived, dict):
        raise PrecomputedStatsError("Precomputed stats snapshot is missing data.derived object.")
    meta = payload.get("meta")
    if meta is not None and not isinstance(meta, dict):
        raise PrecomputedStatsError("Precomputed stats snapshot meta must be an object when present.")
    return payload


def load_precomputed_stats_response(path: Path | None = None) -> dict[str, Any]:
    snapshot_path = path or stats_snapshot_path()
    if not snapshot_path.exists():
        raise PrecomputedStatsError(f"Precomputed stats snapshot not found: {snapshot_path}")

    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PrecomputedStatsError(f"Precomputed stats snapshot is invalid JSON: {exc}") from exc
    except OSError as exc:
        raise PrecomputedStatsError(f"Precomputed stats snapshot could not be read: {exc}") from exc

    validated = deepcopy(_validate_stats_envelope(payload))
    meta = validated.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        validated["meta"] = meta
    meta["stats_backend"] = "precomputed"
    meta["stats_snapshot_path"] = str(snapshot_path)
    return validated
