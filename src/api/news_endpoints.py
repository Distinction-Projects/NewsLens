from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from flask import jsonify, request

from src.services.rss_digest import (
    RssDigestClient,
    RssDigestNotFoundError,
    filter_records,
    parse_snapshot_date,
    sort_records_desc,
)


def _parse_limit(raw_limit: str | None) -> int | None:
    if raw_limit is None or not raw_limit.strip():
        return None

    try:
        limit = int(raw_limit)
    except ValueError as exc:
        raise ValueError("limit must be a positive integer") from exc

    if limit <= 0:
        raise ValueError("limit must be a positive integer")
    return limit


def _common_meta(bundle: dict[str, Any], filtered_count: int, returned_count: int) -> dict:
    return {
        "source_url": bundle["source_url"],
        "source_mode": bundle.get("source_mode"),
        "snapshot_date": bundle.get("snapshot_date"),
        "etag": bundle.get("etag"),
        "schema_version": bundle.get("schema_version"),
        "contract": bundle.get("contract"),
        "generated_at": bundle["generated_at"],
        "digest_generated_at": bundle.get("digest_generated_at"),
        "digest_run_id": bundle.get("digest_run_id"),
        "fetched_at": bundle["fetched_at"],
        "ttl_seconds": bundle["ttl_seconds"],
        "from_cache": bundle["from_cache"],
        "using_last_good": bundle["using_last_good"],
        "fetch_error": bundle["error"],
        "filtered_count": filtered_count,
        "returned_count": returned_count,
    }


def register_news_endpoints(server) -> None:
    client = RssDigestClient()

    @server.get("/api/news/digest")
    def get_news_digest():
        force_refresh = request.args.get("refresh", "").strip().lower() in {"1", "true", "yes"}
        date_filter = request.args.get("date")
        tag_filter = request.args.get("tag")
        source_filter = request.args.get("source")
        raw_limit = request.args.get("limit")
        snapshot_date: str | None = None

        try:
            limit = _parse_limit(raw_limit)
            snapshot_date = parse_snapshot_date(request.args.get("snapshot_date"))
            bundle = client.get_payload(force_refresh=force_refresh, snapshot_date=snapshot_date)
            records = bundle["articles_normalized"]
            filtered = filter_records(records, date_filter=date_filter, tag_filter=tag_filter, source_filter=source_filter)
            ordered = sort_records_desc(filtered)
            if limit is not None:
                ordered = ordered[:limit]
        except ValueError as exc:
            return jsonify({"status": "bad_request", "error": str(exc)}), 400
        except RssDigestNotFoundError as exc:
            if snapshot_date:
                return jsonify({"status": "not_found", "error": str(exc)}), 404
            return jsonify({"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"}), 503
        except Exception as exc:  # noqa: BLE001
            return jsonify({"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"}), 503

        return (
            jsonify(
                {
                    "status": "ok",
                    "filters": {
                        "date": date_filter,
                        "tag": tag_filter,
                        "source": source_filter,
                        "limit": limit,
                        "snapshot_date": snapshot_date,
                    },
                    "meta": _common_meta(bundle, filtered_count=len(filtered), returned_count=len(ordered)),
                    "data": ordered,
                }
            ),
            200,
        )

    @server.get("/api/news/digest/latest")
    def get_latest_news_digest():
        force_refresh = request.args.get("refresh", "").strip().lower() in {"1", "true", "yes"}
        date_filter = request.args.get("date")
        tag_filter = request.args.get("tag")
        source_filter = request.args.get("source")
        snapshot_date: str | None = None

        try:
            snapshot_date = parse_snapshot_date(request.args.get("snapshot_date"))
            bundle = client.get_payload(force_refresh=force_refresh, snapshot_date=snapshot_date)
            records = bundle["articles_normalized"]
            filtered = filter_records(records, date_filter=date_filter, tag_filter=tag_filter, source_filter=source_filter)
            ordered = sort_records_desc(filtered)
        except ValueError as exc:
            return jsonify({"status": "bad_request", "error": str(exc)}), 400
        except RssDigestNotFoundError as exc:
            if snapshot_date:
                return jsonify({"status": "not_found", "error": str(exc)}), 404
            return jsonify({"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"}), 503
        except Exception as exc:  # noqa: BLE001
            return jsonify({"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"}), 503

        if not ordered:
            return (
                jsonify(
                    {
                        "status": "not_found",
                        "filters": {
                            "date": date_filter,
                            "tag": tag_filter,
                            "source": source_filter,
                            "snapshot_date": snapshot_date,
                        },
                        "meta": _common_meta(bundle, filtered_count=0, returned_count=0),
                        "data": None,
                    }
                ),
                404,
            )

        return (
            jsonify(
                {
                    "status": "ok",
                    "filters": {
                        "date": date_filter,
                        "tag": tag_filter,
                        "source": source_filter,
                        "snapshot_date": snapshot_date,
                    },
                    "meta": _common_meta(bundle, filtered_count=len(filtered), returned_count=1),
                    "data": ordered[0],
                }
            ),
            200,
        )

    @server.get("/api/news/stats")
    def get_news_stats():
        force_refresh = request.args.get("refresh", "").strip().lower() in {"1", "true", "yes"}
        snapshot_date: str | None = None

        try:
            snapshot_date = parse_snapshot_date(request.args.get("snapshot_date"))
            bundle = client.get_payload(force_refresh=force_refresh, snapshot_date=snapshot_date)
        except ValueError as exc:
            return jsonify({"status": "bad_request", "error": str(exc)}), 400
        except RssDigestNotFoundError as exc:
            if snapshot_date:
                return jsonify({"status": "not_found", "error": str(exc)}), 404
            return jsonify({"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"}), 503
        except Exception as exc:  # noqa: BLE001
            return jsonify({"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"}), 503

        stats = bundle.get("stats") if isinstance(bundle.get("stats"), dict) else {}

        return (
            jsonify(
                {
                    "status": "ok",
                    "meta": _common_meta(
                        bundle,
                        filtered_count=len(bundle.get("articles_normalized", [])),
                        returned_count=len(bundle.get("articles_normalized", [])),
                    ),
                    "data": {
                        "derived": stats,
                        "summary": bundle.get("summary", {}),
                        "analysis": bundle.get("analysis", {}),
                    },
                }
            ),
            200,
        )

    @server.get("/health/news-freshness")
    def news_freshness_health():
        now_utc = datetime.now(timezone.utc)
        max_age_seconds = client.max_age_seconds

        try:
            bundle = client.get_payload(force_refresh=False)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"}), 503

        generated_at_dt = bundle["generated_at_dt"]
        if generated_at_dt is None:
            return (
                jsonify(
                    {
                        "status": "stale",
                        "is_fresh": False,
                        "reason": "generated_at is missing from payload",
                        "generated_at": None,
                        "age_seconds": None,
                        "max_age_seconds": max_age_seconds,
                        "meta": _common_meta(bundle, filtered_count=0, returned_count=0),
                    }
                ),
                503,
            )

        age_seconds = int((now_utc - generated_at_dt).total_seconds())
        is_fresh = age_seconds <= max_age_seconds
        status_code = 200 if is_fresh else 503

        return (
            jsonify(
                {
                    "status": "ok" if is_fresh else "stale",
                    "is_fresh": is_fresh,
                    "generated_at": bundle["generated_at"],
                    "age_seconds": age_seconds,
                    "max_age_seconds": max_age_seconds,
                    "meta": _common_meta(bundle, filtered_count=0, returned_count=0),
                }
            ),
            status_code,
        )
