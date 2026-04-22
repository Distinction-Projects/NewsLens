from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

CONFIG_PLACEHOLDER_VALUES = {"", "-", "none", "null", "unset", "changeme"}
DB_URL_ENV_KEYS = (
    "DATABASE_URL",
    "SUPABASE_DB_URL",
    "SUPABASE_DIRECT_DB_URL",
    "SUPABASE_DIRECT_CONNECT",
)

_schema_lock = threading.Lock()
_schema_ready = False


def _clean_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in CONFIG_PLACEHOLDER_VALUES:
        return None
    return text


def _timestamp_utc() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _import_psycopg():
    try:
        import psycopg  # type: ignore
    except Exception:
        return None
    return psycopg


def database_url() -> str | None:
    for env_key in DB_URL_ENV_KEYS:
        cleaned = _clean_value(os.getenv(env_key))
        if cleaned:
            return cleaned
    return None


def database_configured() -> bool:
    return database_url() is not None


def _connect_kwargs(url: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"connect_timeout": 5}
    # Supabase direct connections require SSL in normal deployments.
    if "sslmode=" not in url:
        kwargs["sslmode"] = "require"
    return kwargs


def _ensure_schema(conn) -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS public.analysis_runs (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    model TEXT NOT NULL,
                    sentiment TEXT NOT NULL,
                    score DOUBLE PRECISION,
                    input_text TEXT NOT NULL,
                    processed_text TEXT,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_analysis_runs_created_at
                ON public.analysis_runs (created_at DESC);
                """
            )
        conn.commit()
        _schema_ready = True


def database_health_snapshot() -> dict[str, Any]:
    url = database_url()
    if not url:
        return {
            "status": "unconfigured",
            "configured": False,
            "checked_at": _timestamp_utc(),
            "latency_ms": None,
            "error": None,
        }

    psycopg = _import_psycopg()
    if psycopg is None:
        return {
            "status": "driver_unavailable",
            "configured": True,
            "checked_at": _timestamp_utc(),
            "latency_ms": None,
            "error": "psycopg is not installed",
        }

    start = time.perf_counter()
    try:
        with psycopg.connect(url, **_connect_kwargs(url)) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT NOW() AT TIME ZONE 'UTC';")
                row = cur.fetchone()
        elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
        db_time = row[0].isoformat() if row and row[0] else None
        return {
            "status": "ok",
            "configured": True,
            "checked_at": _timestamp_utc(),
            "latency_ms": elapsed_ms,
            "database_time_utc": db_time,
            "error": None,
        }
    except Exception as exc:
        return {
            "status": "error",
            "configured": True,
            "checked_at": _timestamp_utc(),
            "latency_ms": None,
            "error": str(exc),
        }


def persist_analysis_run(
    *,
    model: str,
    sentiment: str,
    score: float | None,
    input_text: str,
    processed_text: str | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = database_url()
    if not url:
        return {"status": "unconfigured", "saved": False, "error": None}

    psycopg = _import_psycopg()
    if psycopg is None:
        return {"status": "driver_unavailable", "saved": False, "error": "psycopg is not installed"}

    meta = metadata or {}
    try:
        with psycopg.connect(url, **_connect_kwargs(url)) as conn:
            _ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.analysis_runs
                        (model, sentiment, score, input_text, processed_text, metadata)
                    VALUES
                        (%s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING id;
                    """,
                    (model, sentiment, score, input_text, processed_text, psycopg.types.json.Jsonb(meta)),
                )
                row = cur.fetchone()
            conn.commit()
        inserted_id = row[0] if row else None
        return {"status": "saved", "saved": True, "id": inserted_id, "error": None}
    except Exception as exc:
        return {"status": "error", "saved": False, "error": str(exc)}
