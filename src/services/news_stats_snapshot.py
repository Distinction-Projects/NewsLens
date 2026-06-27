from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.rss_digest import parse_datetime, strip_excluded_tags_from_payload


DEFAULT_NEWS_STATS_SNAPSHOT_PATH = "data/processed/news_analytics_snapshot.json"
_SNAPSHOT_CACHE_LOCK = threading.Lock()
_SNAPSHOT_CACHE: dict[tuple[str, int, int], dict[str, Any]] = {}


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


def _content_generated_at(payload: dict[str, Any]) -> datetime | None:
    meta = payload.get("meta")
    meta_obj = meta if isinstance(meta, dict) else {}
    for key in ("generated_at", "digest_generated_at"):
        parsed = parse_datetime(meta_obj.get(key))
        if parsed is not None:
            return parsed

    snapshot = payload.get("snapshot")
    snapshot_obj = snapshot if isinstance(snapshot, dict) else {}
    return parse_datetime(snapshot_obj.get("generated_at"))


def _reject_stale_snapshot(payload: dict[str, Any], *, max_age_seconds: int | None) -> None:
    if max_age_seconds is None or max_age_seconds <= 0:
        return

    generated_at = _content_generated_at(payload)
    if generated_at is None:
        raise PrecomputedStatsError("Precomputed stats snapshot freshness timestamp is missing.")

    age_seconds = int((datetime.now(timezone.utc) - generated_at).total_seconds())
    if age_seconds > max_age_seconds:
        raise PrecomputedStatsError(
            f"Precomputed stats snapshot is stale: age_seconds={age_seconds}, max_age_seconds={max_age_seconds}"
        )


def load_precomputed_stats_response(path: Path | None = None, *, max_age_seconds: int | None = None) -> dict[str, Any]:
    snapshot_path = path or stats_snapshot_path()
    try:
        stat = snapshot_path.stat()
    except FileNotFoundError as exc:
        raise PrecomputedStatsError(f"Precomputed stats snapshot not found: {snapshot_path}")
    except OSError as exc:
        raise PrecomputedStatsError(f"Precomputed stats snapshot could not be read: {exc}") from exc

    cache_key = (str(snapshot_path.resolve()), stat.st_mtime_ns, stat.st_size)
    with _SNAPSHOT_CACHE_LOCK:
        cached = _SNAPSHOT_CACHE.get(cache_key)
        if cached is not None:
            return deepcopy(cached)

    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PrecomputedStatsError(f"Precomputed stats snapshot is invalid JSON: {exc}") from exc
    except OSError as exc:
        raise PrecomputedStatsError(f"Precomputed stats snapshot could not be read: {exc}") from exc

    validated = deepcopy(_validate_stats_envelope(payload))
    validated = strip_excluded_tags_from_payload(validated)
    _reject_stale_snapshot(validated, max_age_seconds=max_age_seconds)
    meta = validated.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        validated["meta"] = meta
    meta["stats_backend"] = "precomputed"
    meta["stats_snapshot_path"] = str(snapshot_path)
    with _SNAPSHOT_CACHE_LOCK:
        _SNAPSHOT_CACHE.clear()
        _SNAPSHOT_CACHE[cache_key] = deepcopy(validated)
    return validated
