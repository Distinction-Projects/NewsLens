from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.services.rss_digest import (
    RssDigestClient,
    RssDigestNotFoundError,
    filter_records,
    parse_snapshot_date,
    sort_records_desc,
)
from src.services.news_stats_snapshot import (
    PrecomputedStatsError,
    load_precomputed_stats_response,
    stats_backend_mode,
)


@dataclass
class ControllerResponse:
    status_code: int
    body: dict[str, Any] | str
    content_type: str = "application/json"
    headers: dict[str, str] = field(default_factory=dict)


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


def _parse_refresh(raw_refresh: str | None) -> bool:
    return (raw_refresh or "").strip().lower() in {"1", "true", "yes"}


def _parse_cache_seconds(env_name: str, default: int) -> int:
    raw = os.getenv(env_name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(value, 0)


def _cache_control(max_age: int, stale_seconds: int) -> str:
    if max_age <= 0:
        return "no-store"
    return f"public, max-age={max_age}, stale-while-revalidate={max(stale_seconds, 0)}"


def _read_cache_headers(
    *,
    force_refresh: bool,
    snapshot_date: str | None,
    seconds_env: str = "NEWS_HTTP_CACHE_SECONDS",
    default_seconds: int = 300,
) -> dict[str, str]:
    if force_refresh:
        return {"Cache-Control": "no-store"}
    if snapshot_date:
        max_age = _parse_cache_seconds("NEWS_SNAPSHOT_HTTP_CACHE_SECONDS", 86400)
        stale_seconds = _parse_cache_seconds("NEWS_SNAPSHOT_HTTP_STALE_SECONDS", 604800)
    else:
        max_age = _parse_cache_seconds(seconds_env, default_seconds)
        stale_seconds = _parse_cache_seconds("NEWS_HTTP_STALE_SECONDS", 3600)
    return {"Cache-Control": _cache_control(max_age, stale_seconds)}


def _no_store_headers() -> dict[str, str]:
    return {"Cache-Control": "no-store"}


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
        "input_articles_count": bundle.get("input_articles_count"),
        "excluded_unscraped_articles": bundle.get("excluded_unscraped_articles"),
        "filtered_count": filtered_count,
        "returned_count": returned_count,
    }


def _select_lens_correlations(bundle: dict[str, Any]) -> dict[str, Any]:
    analysis = bundle.get("analysis")
    analysis_obj = analysis if isinstance(analysis, dict) else {}
    upstream = analysis_obj.get("lens_correlations")
    if isinstance(upstream, dict) and isinstance(upstream.get("lenses"), list) and upstream.get("lenses"):
        return upstream

    stats = bundle.get("stats")
    stats_obj = stats if isinstance(stats, dict) else {}
    derived = stats_obj.get("lens_correlations")
    if isinstance(derived, dict):
        return derived
    return {}


def _matrix_pair_rows(lens_correlations: dict[str, Any]) -> list[dict[str, Any]]:
    lenses = lens_correlations.get("lenses")
    lens_names = [name for name in lenses if isinstance(name, str)] if isinstance(lenses, list) else []
    size = len(lens_names)
    if size == 0:
        return []

    correlation = lens_correlations.get("correlation") if isinstance(lens_correlations.get("correlation"), dict) else {}
    covariance = lens_correlations.get("covariance") if isinstance(lens_correlations.get("covariance"), dict) else {}
    corr_raw = correlation.get("raw") if isinstance(correlation.get("raw"), list) else []
    corr_norm = correlation.get("normalized") if isinstance(correlation.get("normalized"), list) else []
    cov_raw = covariance.get("raw") if isinstance(covariance.get("raw"), list) else []
    cov_norm = covariance.get("normalized") if isinstance(covariance.get("normalized"), list) else []
    pair_counts = lens_correlations.get("pairwise_counts") if isinstance(lens_correlations.get("pairwise_counts"), list) else []

    def _value(matrix: list, row_idx: int, col_idx: int):
        if row_idx >= len(matrix) or not isinstance(matrix[row_idx], list):
            return None
        row = matrix[row_idx]
        if col_idx >= len(row):
            return None
        return row[col_idx]

    rows: list[dict[str, Any]] = []
    for row_idx, lens_a in enumerate(lens_names):
        for col_idx in range(row_idx, size):
            lens_b = lens_names[col_idx]
            rows.append(
                {
                    "lens_a": lens_a,
                    "lens_b": lens_b,
                    "correlation_raw": _value(corr_raw, row_idx, col_idx),
                    "correlation_normalized": _value(corr_norm, row_idx, col_idx),
                    "covariance_raw": _value(cov_raw, row_idx, col_idx),
                    "covariance_normalized": _value(cov_norm, row_idx, col_idx),
                    "pairwise_count": _value(pair_counts, row_idx, col_idx),
                }
            )
    return rows


def _export_rows_for_artifact(bundle: dict[str, Any], artifact: str) -> list[dict[str, Any]]:
    stats = bundle.get("stats")
    stats_obj = stats if isinstance(stats, dict) else {}
    chart_aggregates = stats_obj.get("chart_aggregates") if isinstance(stats_obj.get("chart_aggregates"), dict) else {}

    if artifact == "source_tag_matrix":
        rows = chart_aggregates.get("source_tag_matrix")
        return rows if isinstance(rows, list) else []
    if artifact == "source_score_status":
        rows = chart_aggregates.get("score_status_by_source")
        return rows if isinstance(rows, list) else []
    if artifact == "lens_pair_metrics":
        return _matrix_pair_rows(_select_lens_correlations(bundle))
    if artifact == "source_lens_effects":
        rows = stats_obj.get("source_lens_effects") if isinstance(stats_obj.get("source_lens_effects"), dict) else {}
        effect_rows = rows.get("rows") if isinstance(rows.get("rows"), list) else []
        return effect_rows
    if artifact == "source_differentiation_summary":
        source_diff = stats_obj.get("source_differentiation") if isinstance(stats_obj.get("source_differentiation"), dict) else {}
        classification = source_diff.get("classification") if isinstance(source_diff.get("classification"), dict) else {}
        multivariate = source_diff.get("multivariate") if isinstance(source_diff.get("multivariate"), dict) else {}
        source_counts = source_diff.get("source_counts") if isinstance(source_diff.get("source_counts"), dict) else {}
        return [
            {
                "status": source_diff.get("status"),
                "reason": source_diff.get("reason"),
                "n_articles": source_diff.get("n_articles"),
                "n_sources": source_diff.get("n_sources"),
                "n_lenses": source_diff.get("n_lenses"),
                "permutations": source_diff.get("permutations"),
                "multivariate_f_stat": multivariate.get("f_stat"),
                "multivariate_r_squared": multivariate.get("r_squared"),
                "multivariate_p_perm": multivariate.get("p_perm"),
                "classification_accuracy": classification.get("accuracy"),
                "classification_baseline_accuracy": classification.get("baseline_accuracy"),
                "classification_p_perm": classification.get("p_perm"),
                "source_counts": source_counts,
            }
        ]
    return []


def _rows_to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""

    headers = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def _response_json(status_code: int, body: dict[str, Any], headers: dict[str, str] | None = None) -> ControllerResponse:
    return ControllerResponse(status_code=status_code, body=body, headers=headers or {})


class NewsController:
    def __init__(self, client: RssDigestClient) -> None:
        self.client = client

    def get_digest(
        self,
        *,
        refresh: str | None,
        date: str | None,
        tag: str | None,
        source: str | None,
        limit: str | None,
        snapshot_date: str | None,
    ) -> ControllerResponse:
        force_refresh = _parse_refresh(refresh)
        snapshot_date_value: str | None = None
        try:
            parsed_limit = _parse_limit(limit)
            snapshot_date_value = parse_snapshot_date(snapshot_date)
            bundle = self.client.get_payload(force_refresh=force_refresh, snapshot_date=snapshot_date_value)
            records = bundle["articles_normalized"]
            filtered = filter_records(records, date_filter=date, tag_filter=tag, source_filter=source)
            ordered = sort_records_desc(filtered)
            if parsed_limit is not None:
                ordered = ordered[:parsed_limit]
        except ValueError as exc:
            return _response_json(400, {"status": "bad_request", "error": str(exc)})
        except RssDigestNotFoundError as exc:
            if snapshot_date_value:
                return _response_json(404, {"status": "not_found", "error": str(exc)})
            return _response_json(503, {"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"})
        except Exception as exc:  # noqa: BLE001
            return _response_json(503, {"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"})

        return _response_json(
            200,
            {
                "status": "ok",
                "filters": {
                    "date": date,
                    "tag": tag,
                    "source": source,
                    "limit": parsed_limit,
                    "snapshot_date": snapshot_date_value,
                },
                "meta": _common_meta(bundle, filtered_count=len(filtered), returned_count=len(ordered)),
                "data": ordered,
            },
            headers=_read_cache_headers(force_refresh=force_refresh, snapshot_date=snapshot_date_value),
        )

    def get_latest_digest(
        self,
        *,
        refresh: str | None,
        date: str | None,
        tag: str | None,
        source: str | None,
        snapshot_date: str | None,
    ) -> ControllerResponse:
        force_refresh = _parse_refresh(refresh)
        snapshot_date_value: str | None = None
        try:
            snapshot_date_value = parse_snapshot_date(snapshot_date)
            bundle = self.client.get_payload(force_refresh=force_refresh, snapshot_date=snapshot_date_value)
            records = bundle["articles_normalized"]
            filtered = filter_records(records, date_filter=date, tag_filter=tag, source_filter=source)
            ordered = sort_records_desc(filtered)
        except ValueError as exc:
            return _response_json(400, {"status": "bad_request", "error": str(exc)})
        except RssDigestNotFoundError as exc:
            if snapshot_date_value:
                return _response_json(404, {"status": "not_found", "error": str(exc)})
            return _response_json(503, {"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"})
        except Exception as exc:  # noqa: BLE001
            return _response_json(503, {"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"})

        if not ordered:
            return _response_json(
                404,
                {
                    "status": "not_found",
                    "filters": {
                        "date": date,
                        "tag": tag,
                        "source": source,
                        "snapshot_date": snapshot_date_value,
                    },
                    "meta": _common_meta(bundle, filtered_count=0, returned_count=0),
                    "data": None,
                },
            )

        return _response_json(
            200,
            {
                "status": "ok",
                "filters": {
                    "date": date,
                    "tag": tag,
                    "source": source,
                    "snapshot_date": snapshot_date_value,
                },
                "meta": _common_meta(bundle, filtered_count=len(filtered), returned_count=1),
                "data": ordered[0],
            },
            headers=_read_cache_headers(force_refresh=force_refresh, snapshot_date=snapshot_date_value),
        )

    def get_stats(self, *, refresh: str | None, snapshot_date: str | None) -> ControllerResponse:
        force_refresh = _parse_refresh(refresh)
        snapshot_date_value: str | None = None

        try:
            snapshot_date_value = parse_snapshot_date(snapshot_date)
            if snapshot_date_value is None and stats_backend_mode() == "precomputed":
                return _response_json(
                    200,
                    load_precomputed_stats_response(),
                    headers=_read_cache_headers(
                        force_refresh=force_refresh,
                        snapshot_date=None,
                        seconds_env="NEWS_STATS_HTTP_CACHE_SECONDS",
                        default_seconds=300,
                    ),
                )
            bundle = self.client.get_payload(force_refresh=force_refresh, snapshot_date=snapshot_date_value)
        except ValueError as exc:
            return _response_json(400, {"status": "bad_request", "error": str(exc)})
        except PrecomputedStatsError as exc:
            return _response_json(
                503,
                {"status": "precomputed_stats_unavailable", "error": str(exc), "data": None},
                headers=_no_store_headers(),
            )
        except RssDigestNotFoundError as exc:
            if snapshot_date_value:
                return _response_json(404, {"status": "not_found", "error": str(exc)})
            return _response_json(503, {"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"})
        except Exception as exc:  # noqa: BLE001
            return _response_json(503, {"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"})

        stats = bundle.get("stats") if isinstance(bundle.get("stats"), dict) else {}
        article_count = len(bundle.get("articles_normalized", []))
        return _response_json(
            200,
            {
                "status": "ok",
                "meta": _common_meta(bundle, filtered_count=article_count, returned_count=article_count),
                "data": {
                    "derived": stats,
                    "summary": bundle.get("summary", {}),
                    "analysis": bundle.get("analysis", {}),
                },
            },
            headers=_read_cache_headers(
                force_refresh=force_refresh,
                snapshot_date=snapshot_date_value,
                seconds_env="NEWS_STATS_HTTP_CACHE_SECONDS",
                default_seconds=300,
            ),
        )

    def get_upstream(self, *, refresh: str | None, snapshot_date: str | None) -> ControllerResponse:
        force_refresh = _parse_refresh(refresh)
        snapshot_date_value: str | None = None

        try:
            snapshot_date_value = parse_snapshot_date(snapshot_date)
            bundle = self.client.get_payload(force_refresh=force_refresh, snapshot_date=snapshot_date_value)
        except ValueError as exc:
            return _response_json(400, {"status": "bad_request", "error": str(exc)})
        except RssDigestNotFoundError as exc:
            if snapshot_date_value:
                return _response_json(404, {"status": "not_found", "error": str(exc)})
            return _response_json(503, {"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"})
        except Exception as exc:  # noqa: BLE001
            return _response_json(503, {"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"})

        article_count = len(bundle.get("articles_normalized", []))
        return _response_json(
            200,
            {
                "status": "ok",
                "meta": _common_meta(bundle, filtered_count=article_count, returned_count=article_count),
                "data": {
                    "upstream": bundle.get("upstream_payload"),
                },
            },
            headers=_read_cache_headers(force_refresh=force_refresh, snapshot_date=snapshot_date_value),
        )

    def export_artifact(
        self,
        *,
        refresh: str | None,
        artifact: str | None,
        export_format: str | None,
        snapshot_date: str | None,
    ) -> ControllerResponse:
        force_refresh = _parse_refresh(refresh)
        snapshot_date_value: str | None = None
        artifact_value = (artifact or "").strip()
        export_format_value = (export_format or "csv").strip().lower()

        allowed_artifacts = {
            "source_tag_matrix",
            "source_score_status",
            "lens_pair_metrics",
            "source_lens_effects",
            "source_differentiation_summary",
        }
        if artifact_value not in allowed_artifacts:
            return _response_json(
                400,
                {
                    "status": "bad_request",
                    "error": f"artifact must be one of {sorted(allowed_artifacts)}",
                },
            )

        if export_format_value not in {"csv", "json"}:
            return _response_json(400, {"status": "bad_request", "error": "format must be csv or json"})

        try:
            snapshot_date_value = parse_snapshot_date(snapshot_date)
            bundle = self.client.get_payload(force_refresh=force_refresh, snapshot_date=snapshot_date_value)
        except ValueError as exc:
            return _response_json(400, {"status": "bad_request", "error": str(exc)})
        except RssDigestNotFoundError as exc:
            if snapshot_date_value:
                return _response_json(404, {"status": "not_found", "error": str(exc)})
            return _response_json(503, {"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"})
        except Exception as exc:  # noqa: BLE001
            return _response_json(503, {"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"})

        rows = _export_rows_for_artifact(bundle, artifact_value)
        meta = _common_meta(bundle, filtered_count=len(rows), returned_count=len(rows))

        if export_format_value == "json":
            return _response_json(
                200,
                {
                    "status": "ok",
                    "artifact": artifact_value,
                    "format": "json",
                    "meta": meta,
                    "rows": rows,
                },
                headers=_read_cache_headers(force_refresh=force_refresh, snapshot_date=snapshot_date_value),
            )

        csv_payload = _rows_to_csv(rows)
        return ControllerResponse(
            status_code=200,
            body=csv_payload,
            content_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{artifact_value}.csv"',
                **_read_cache_headers(force_refresh=force_refresh, snapshot_date=snapshot_date_value),
            },
        )

    def get_news_freshness(self) -> ControllerResponse:
        now_utc = datetime.now(timezone.utc)
        max_age_seconds = self.client.max_age_seconds

        try:
            bundle = self.client.get_payload(force_refresh=False)
        except Exception as exc:  # noqa: BLE001
            return _response_json(503, {"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"})

        generated_at_dt = bundle["generated_at_dt"]
        if generated_at_dt is None:
            return _response_json(
                503,
                {
                    "status": "stale",
                    "is_fresh": False,
                    "reason": "generated_at is missing from payload",
                    "generated_at": None,
                    "age_seconds": None,
                    "max_age_seconds": max_age_seconds,
                    "meta": _common_meta(bundle, filtered_count=0, returned_count=0),
                },
            )

        age_seconds = int((now_utc - generated_at_dt).total_seconds())
        is_fresh = age_seconds <= max_age_seconds
        status_code = 200 if is_fresh else 503

        return _response_json(
            status_code,
            {
                "status": "ok" if is_fresh else "stale",
                "is_fresh": is_fresh,
                "generated_at": bundle["generated_at"],
                "age_seconds": age_seconds,
                "max_age_seconds": max_age_seconds,
                "meta": _common_meta(bundle, filtered_count=0, returned_count=0),
            },
        )
