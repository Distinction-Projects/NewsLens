from __future__ import annotations

import csv
import io
import json
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


def _stats_obj_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    stats = payload.get("stats")
    if isinstance(stats, dict):
        return stats
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("derived"), dict):
        return data["derived"]
    return {}


def _analysis_obj_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = payload.get("analysis")
    if isinstance(analysis, dict):
        return analysis
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("analysis"), dict):
        return data["analysis"]
    return {}


def _export_meta_from_payload(payload: dict[str, Any], filtered_count: int, returned_count: int) -> dict[str, Any]:
    if "source_url" in payload and "fetched_at" in payload:
        return _common_meta(payload, filtered_count=filtered_count, returned_count=returned_count)
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    return {
        **meta,
        "filtered_count": filtered_count,
        "returned_count": returned_count,
    }


def _mark_precomputed_fallback(meta: dict[str, Any], error: PrecomputedStatsError) -> dict[str, Any]:
    meta["stats_backend"] = "dynamic"
    meta["stats_backend_fallback"] = "precomputed_unavailable"
    meta["precomputed_stats_error"] = str(error)
    return meta


def _select_lens_correlations(payload: dict[str, Any]) -> dict[str, Any]:
    analysis_obj = _analysis_obj_from_payload(payload)
    upstream = analysis_obj.get("lens_correlations")
    if isinstance(upstream, dict) and isinstance(upstream.get("lenses"), list) and upstream.get("lenses"):
        return upstream

    stats_obj = _stats_obj_from_payload(payload)
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


def _source_differentiation_summary_rows(source_diff: dict[str, Any]) -> list[dict[str, Any]]:
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


def _movement_pattern_label(
    total_movement: Any,
    largest_jump: Any,
    valid_bucket_count: Any,
) -> tuple[str | None, float | None]:
    if not isinstance(total_movement, (int, float)) or not isinstance(largest_jump, (int, float)):
        return None, None

    if float(total_movement) <= 0:
        return "no measurable movement", None

    jump_share = min(max(float(largest_jump) / float(total_movement), 0.0), 1.0)
    if jump_share >= 0.75:
        return "jump-led", jump_share
    if int(valid_bucket_count or 0) >= 3 and jump_share <= 0.6:
        return "steady drift", jump_share
    return "mixed", jump_share


def _group_temporal_pattern_fields(
    path_summary: dict[str, Any],
    *,
    prefix: str = "",
) -> dict[str, Any]:
    pca_label, pca_jump_share = _movement_pattern_label(
        path_summary.get("total_movement_pca"),
        path_summary.get("largest_jump_pca"),
        path_summary.get("valid_pca_bucket_count"),
    )
    mds_label, mds_jump_share = _movement_pattern_label(
        path_summary.get("total_movement_mds"),
        path_summary.get("largest_jump_mds"),
        path_summary.get("valid_mds_bucket_count"),
    )
    return {
        f"{prefix}movement_pattern_pca": pca_label,
        f"{prefix}largest_jump_share_pca": pca_jump_share,
        f"{prefix}movement_pattern_mds": mds_label,
        f"{prefix}largest_jump_share_mds": mds_jump_share,
    }


def _group_temporal_popularity_fields(
    popularity_summary: dict[str, Any],
    *,
    prefix: str = "",
) -> dict[str, Any]:
    return {
        f"{prefix}popularity_peak_bucket": popularity_summary.get("peak_bucket"),
        f"{prefix}popularity_peak_articles": popularity_summary.get("peak_articles"),
        f"{prefix}popularity_first_share": popularity_summary.get("first_share"),
        f"{prefix}popularity_latest_share": popularity_summary.get("latest_share"),
        f"{prefix}popularity_share_delta": popularity_summary.get("share_delta"),
        f"{prefix}popularity_recent_share_delta": popularity_summary.get("recent_share_delta"),
        f"{prefix}popularity_first_share_rank_within_type": popularity_summary.get("first_share_rank"),
        f"{prefix}popularity_latest_share_rank_within_type": popularity_summary.get("latest_share_rank"),
        f"{prefix}popularity_rank_change_within_type": popularity_summary.get("rank_change"),
    }


def _share_delta_direction(value: Any) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    if abs(float(value)) < 0.0005:
        return "flat"
    return "rising" if float(value) > 0 else "falling"


def _popularity_momentum_label(share_delta: Any, recent_share_delta: Any) -> str | None:
    overall_direction = _share_delta_direction(share_delta)
    recent_direction = _share_delta_direction(recent_share_delta)

    if overall_direction == "rising":
        if recent_direction == "rising":
            return "rising now"
        if recent_direction == "falling":
            return "cooling after gains"
        return "holding gains"
    if overall_direction == "falling":
        if recent_direction == "rising":
            return "rebounding"
        if recent_direction == "falling":
            return "still falling"
        return "holding losses"
    if overall_direction == "flat":
        if recent_direction == "rising":
            return "rebounding to baseline"
        if recent_direction == "falling":
            return "slipping from baseline"
        return "flat"
    if recent_direction == "rising":
        return "recently rising"
    if recent_direction == "falling":
        return "recently falling"
    return recent_direction


def _group_temporal_path_summary_rows(group_temporal: dict[str, Any]) -> list[dict[str, Any]]:
    groups = group_temporal.get("groups") if isinstance(group_temporal.get("groups"), dict) else {}
    config = group_temporal.get("config") if isinstance(group_temporal.get("config"), dict) else {}
    rows: list[dict[str, Any]] = []

    for group_type in ("source", "topic", "tag"):
        temporal_rows = groups.get(group_type) if isinstance(groups.get(group_type), list) else []
        for temporal_row in temporal_rows:
            if not isinstance(temporal_row, dict):
                continue

            path_summary = (
                temporal_row.get("path_summary")
                if isinstance(temporal_row.get("path_summary"), dict)
                else {}
            )
            popularity_summary = (
                temporal_row.get("popularity_summary")
                if isinstance(temporal_row.get("popularity_summary"), dict)
                else {}
            )
            coverage_gap_ranges = (
                path_summary.get("coverage_gap_ranges")
                if isinstance(path_summary.get("coverage_gap_ranges"), list)
                else []
            )
            coverage_gap_labels = [
                str(gap.get("label") or "").strip()
                for gap in coverage_gap_ranges
                if isinstance(gap, dict) and str(gap.get("label") or "").strip()
            ]
            direction_pca = path_summary.get("direction_pca") if isinstance(path_summary.get("direction_pca"), dict) else {}
            direction_mds = path_summary.get("direction_mds") if isinstance(path_summary.get("direction_mds"), dict) else {}

            rows.append(
                {
                    "group_type": group_type,
                    "group": temporal_row.get("group"),
                    "group_key": temporal_row.get("group_key"),
                    "status": temporal_row.get("status"),
                    "reason": temporal_row.get("reason"),
                    "bucket_granularity": config.get("bucket_granularity"),
                    "min_articles_per_bucket": config.get("min_articles_per_bucket"),
                    "min_buckets_per_group": config.get("min_buckets_per_group"),
                    "n_articles": temporal_row.get("n_articles"),
                    "n_buckets": temporal_row.get("n_buckets"),
                    "date_start": temporal_row.get("date_start"),
                    "date_end": temporal_row.get("date_end"),
                    "bucket_count": path_summary.get("bucket_count"),
                    "valid_pca_bucket_count": path_summary.get("valid_pca_bucket_count"),
                    "valid_mds_bucket_count": path_summary.get("valid_mds_bucket_count"),
                    "sparse_bucket_count": path_summary.get("sparse_bucket_count"),
                    "coverage_gap_count": path_summary.get("coverage_gap_count"),
                    "coverage_gap_labels": " | ".join(coverage_gap_labels),
                    "coverage_gap_ranges_json": json.dumps(coverage_gap_ranges, sort_keys=True),
                    "start_bucket": path_summary.get("start_bucket"),
                    "end_bucket": path_summary.get("end_bucket"),
                    "total_movement_pca": path_summary.get("total_movement_pca"),
                    "largest_jump_pca": path_summary.get("largest_jump_pca"),
                    "direction_pca_pc1_delta": direction_pca.get("pc1_delta"),
                    "direction_pca_pc2_delta": direction_pca.get("pc2_delta"),
                    "direction_pca_pc3_delta": direction_pca.get("pc3_delta"),
                    "total_movement_mds": path_summary.get("total_movement_mds"),
                    "largest_jump_mds": path_summary.get("largest_jump_mds"),
                    "direction_mds_mds1_delta": direction_mds.get("mds1_delta"),
                    "direction_mds_mds2_delta": direction_mds.get("mds2_delta"),
                    "direction_mds_mds3_delta": direction_mds.get("mds3_delta"),
                    **_group_temporal_pattern_fields(path_summary),
                    **_group_temporal_popularity_fields(popularity_summary),
                }
            )

    return rows


def _rank_group_temporal_popularity_rows(
    rows: list[dict[str, Any]],
    *,
    metric_field: str,
    rank_field: str,
) -> None:
    grouped_rows: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        group_type = str(row.get("group_type") or "").strip().lower()
        if not group_type:
            continue
        grouped_rows.setdefault(group_type, []).append(row)

    for grouped in grouped_rows.values():
        ranked = [
            row
            for row in grouped
            if isinstance(row.get(metric_field), (int, float))
        ]
        ranked.sort(
            key=lambda row: (
                -float(row.get(metric_field) or 0.0),
                -float(
                    row.get("popularity_recent_share_delta")
                    if isinstance(row.get("popularity_recent_share_delta"), (int, float))
                    else -999.0
                ),
                -int(row.get("popularity_peak_articles") or 0),
                -int(row.get("n_articles") or 0),
                str(row.get("group") or "").lower(),
            )
        )
        for index, row in enumerate(ranked, start=1):
            row[rank_field] = index


def _group_temporal_popularity_momentum_rows(group_temporal: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path_row in _group_temporal_path_summary_rows(group_temporal):
        share_delta = path_row.get("popularity_share_delta")
        recent_share_delta = path_row.get("popularity_recent_share_delta")
        if not isinstance(share_delta, (int, float)) and not isinstance(recent_share_delta, (int, float)):
            continue
        rows.append(
            {
                **path_row,
                "popularity_share_direction": _share_delta_direction(share_delta),
                "popularity_recent_share_direction": _share_delta_direction(recent_share_delta),
                "popularity_momentum_label": _popularity_momentum_label(share_delta, recent_share_delta),
                "popularity_first_share_rank_within_type": path_row.get("popularity_first_share_rank_within_type"),
                "popularity_latest_share_rank_within_type": path_row.get("popularity_latest_share_rank_within_type"),
                "popularity_rank_change_within_type": path_row.get("popularity_rank_change_within_type"),
                "popularity_share_delta_rank_within_type": None,
                "popularity_recent_share_delta_rank_within_type": None,
            }
        )

    _rank_group_temporal_popularity_rows(
        rows,
        metric_field="popularity_share_delta",
        rank_field="popularity_share_delta_rank_within_type",
    )
    _rank_group_temporal_popularity_rows(
        rows,
        metric_field="popularity_first_share",
        rank_field="popularity_first_share_rank_within_type",
    )
    _rank_group_temporal_popularity_rows(
        rows,
        metric_field="popularity_latest_share",
        rank_field="popularity_latest_share_rank_within_type",
    )
    _rank_group_temporal_popularity_rows(
        rows,
        metric_field="popularity_recent_share_delta",
        rank_field="popularity_recent_share_delta_rank_within_type",
    )
    for row in rows:
        first_rank = row.get("popularity_first_share_rank_within_type")
        latest_rank = row.get("popularity_latest_share_rank_within_type")
        if isinstance(first_rank, int) and isinstance(latest_rank, int):
            row["popularity_rank_change_within_type"] = int(first_rank) - int(latest_rank)
    rows.sort(
        key=lambda row: (
            str(row.get("group_type") or ""),
            int(row.get("popularity_share_delta_rank_within_type") or 999999),
            int(row.get("popularity_recent_share_delta_rank_within_type") or 999999),
            str(row.get("group") or "").lower(),
        )
    )
    return rows


def _group_temporal_bucket_rows(group_temporal: dict[str, Any]) -> list[dict[str, Any]]:
    groups = group_temporal.get("groups") if isinstance(group_temporal.get("groups"), dict) else {}
    config = group_temporal.get("config") if isinstance(group_temporal.get("config"), dict) else {}
    rows: list[dict[str, Any]] = []

    for group_type in ("source", "topic", "tag"):
        temporal_rows = groups.get(group_type) if isinstance(groups.get(group_type), list) else []
        for temporal_row in temporal_rows:
            if not isinstance(temporal_row, dict):
                continue

            path_summary = (
                temporal_row.get("path_summary")
                if isinstance(temporal_row.get("path_summary"), dict)
                else {}
            )
            popularity_summary = (
                temporal_row.get("popularity_summary")
                if isinstance(temporal_row.get("popularity_summary"), dict)
                else {}
            )
            coverage_gap_ranges = (
                path_summary.get("coverage_gap_ranges")
                if isinstance(path_summary.get("coverage_gap_ranges"), list)
                else []
            )
            coverage_gap_labels = [
                str(gap.get("label") or "").strip()
                for gap in coverage_gap_ranges
                if isinstance(gap, dict) and str(gap.get("label") or "").strip()
            ]
            bucket_rows = temporal_row.get("buckets") if isinstance(temporal_row.get("buckets"), list) else []

            for bucket_row in bucket_rows:
                if not isinstance(bucket_row, dict):
                    continue

                source_counts = (
                    bucket_row.get("source_counts")
                    if isinstance(bucket_row.get("source_counts"), dict)
                    else {}
                )
                top_lens_deviations = (
                    bucket_row.get("top_lens_deviations")
                    if isinstance(bucket_row.get("top_lens_deviations"), list)
                    else []
                )
                top_lens_labels = [
                    str(row.get("lens") or "").strip()
                    for row in top_lens_deviations
                    if isinstance(row, dict) and str(row.get("lens") or "").strip()
                ]

                rows.append(
                    {
                        "group_type": group_type,
                        "group": temporal_row.get("group"),
                        "group_key": temporal_row.get("group_key"),
                        "group_status": temporal_row.get("status"),
                        "group_reason": temporal_row.get("reason"),
                        "bucket_granularity": config.get("bucket_granularity"),
                        "min_articles_per_bucket": config.get("min_articles_per_bucket"),
                        "min_buckets_per_group": config.get("min_buckets_per_group"),
                        "group_n_articles": temporal_row.get("n_articles"),
                        "group_n_buckets": temporal_row.get("n_buckets"),
                        "group_date_start": temporal_row.get("date_start"),
                        "group_date_end": temporal_row.get("date_end"),
                        "group_valid_pca_bucket_count": path_summary.get("valid_pca_bucket_count"),
                        "group_valid_mds_bucket_count": path_summary.get("valid_mds_bucket_count"),
                        "group_sparse_bucket_count": path_summary.get("sparse_bucket_count"),
                        "group_coverage_gap_count": path_summary.get("coverage_gap_count"),
                        "group_coverage_gap_labels": " | ".join(coverage_gap_labels),
                        "group_coverage_gap_ranges_json": json.dumps(coverage_gap_ranges, sort_keys=True),
                        "bucket_start": bucket_row.get("bucket_start"),
                        "bucket_end": bucket_row.get("bucket_end"),
                        "bucket_label": bucket_row.get("bucket_label"),
                        "bucket_status": bucket_row.get("status"),
                        "bucket_n_articles": bucket_row.get("n_articles"),
                        "bucket_n_sources": bucket_row.get("n_sources"),
                        "bucket_corpus_share": bucket_row.get("corpus_share"),
                        "bucket_pc1": bucket_row.get("pc1"),
                        "bucket_pc2": bucket_row.get("pc2"),
                        "bucket_pc3": bucket_row.get("pc3"),
                        "bucket_mds1": bucket_row.get("mds1"),
                        "bucket_mds2": bucket_row.get("mds2"),
                        "bucket_mds3": bucket_row.get("mds3"),
                        "bucket_dispersion_pca": bucket_row.get("dispersion_pca"),
                        "bucket_dispersion_mds": bucket_row.get("dispersion_mds"),
                        "bucket_source_counts_json": json.dumps(source_counts, sort_keys=True),
                        "bucket_top_lens_labels": " | ".join(top_lens_labels),
                        "bucket_top_lens_deviations_json": json.dumps(top_lens_deviations, sort_keys=True),
                        **_group_temporal_pattern_fields(path_summary, prefix="group_"),
                        **_group_temporal_popularity_fields(popularity_summary, prefix="group_"),
                    }
                )

    return rows


def _normalize_group_temporal_bucket_filters(
    artifact: str,
    group_type: str | None,
    group_key: str | None,
    bucket_label: str | None,
) -> tuple[str | None, str | None, str | None]:
    normalized_group_type = str(group_type or "").strip().lower() or None
    normalized_group_key = str(group_key or "").strip() or None
    normalized_bucket_label = str(bucket_label or "").strip() or None

    if normalized_group_type is None and normalized_group_key is None and normalized_bucket_label is None:
        return None, None, None

    if (
        normalized_group_type is not None or normalized_group_key is not None
    ) and artifact not in {"group_temporal_buckets", "group_temporal_path_summary", "group_temporal_popularity_momentum"}:
        raise ValueError(
            "group_type and group_key are only supported for artifact=group_temporal_buckets, artifact=group_temporal_path_summary, or artifact=group_temporal_popularity_momentum"
        )

    if normalized_bucket_label is not None and artifact != "group_temporal_buckets":
        raise ValueError("bucket_label is only supported for artifact=group_temporal_buckets")

    if normalized_group_key and not normalized_group_type:
        raise ValueError("group_key requires group_type")

    if normalized_group_type is not None and normalized_group_type not in {"source", "topic", "tag"}:
        raise ValueError("group_type must be one of ['source', 'tag', 'topic']")

    return normalized_group_type, normalized_group_key, normalized_bucket_label


def _canonicalize_group_filter_key(value: str | None) -> str:
    normalized = str(value or "").strip().lower().replace("-", " ").replace("_", " ")
    return " ".join(normalized.split())


def _filter_group_temporal_bucket_rows(
    rows: list[dict[str, Any]],
    *,
    group_type: str | None,
    group_key: str | None,
    bucket_label: str | None = None,
) -> list[dict[str, Any]]:
    normalized_group_type = str(group_type or "").strip().lower()
    normalized_group_key = _canonicalize_group_filter_key(group_key)
    normalized_bucket_label = str(bucket_label or "").strip()
    if not normalized_group_type:
        if not normalized_bucket_label:
            return rows
        return [
            row
            for row in rows
            if isinstance(row, dict) and str(row.get("bucket_label") or "").strip() == normalized_bucket_label
        ]

    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_group_type = str(row.get("group_type") or "").strip().lower()
        if row_group_type != normalized_group_type:
            continue
        if normalized_group_key:
            row_group_key = _canonicalize_group_filter_key(str(row.get("group_key") or row.get("group") or ""))
            if row_group_key != normalized_group_key:
                continue
        if normalized_bucket_label and str(row.get("bucket_label") or "").strip() != normalized_bucket_label:
            continue
        filtered_rows.append(row)
    return filtered_rows


def _export_rows_for_artifact(payload: dict[str, Any], artifact: str) -> list[dict[str, Any]]:
    stats_obj = _stats_obj_from_payload(payload)
    chart_aggregates = stats_obj.get("chart_aggregates") if isinstance(stats_obj.get("chart_aggregates"), dict) else {}

    if artifact == "source_tag_matrix":
        rows = chart_aggregates.get("source_tag_matrix")
        return rows if isinstance(rows, list) else []
    if artifact == "source_score_status":
        rows = chart_aggregates.get("score_status_by_source")
        return rows if isinstance(rows, list) else []
    if artifact == "lens_pair_metrics":
        return _matrix_pair_rows(_select_lens_correlations(payload))
    if artifact == "source_lens_effects":
        rows = stats_obj.get("source_lens_effects") if isinstance(stats_obj.get("source_lens_effects"), dict) else {}
        effect_rows = rows.get("rows") if isinstance(rows.get("rows"), list) else []
        return effect_rows
    if artifact == "source_differentiation_summary":
        source_diff = stats_obj.get("source_differentiation") if isinstance(stats_obj.get("source_differentiation"), dict) else {}
        return _source_differentiation_summary_rows(source_diff)
    if artifact == "group_temporal_path_summary":
        group_temporal = (
            stats_obj.get("group_temporal_latent_space")
            if isinstance(stats_obj.get("group_temporal_latent_space"), dict)
            else {}
        )
        return _group_temporal_path_summary_rows(group_temporal)
    if artifact == "group_temporal_popularity_momentum":
        group_temporal = (
            stats_obj.get("group_temporal_latent_space")
            if isinstance(stats_obj.get("group_temporal_latent_space"), dict)
            else {}
        )
        return _group_temporal_popularity_momentum_rows(group_temporal)
    if artifact == "group_temporal_buckets":
        group_temporal = (
            stats_obj.get("group_temporal_latent_space")
            if isinstance(stats_obj.get("group_temporal_latent_space"), dict)
            else {}
        )
        return _group_temporal_bucket_rows(group_temporal)
    if artifact == "event_clusters":
        event_control = stats_obj.get("event_control") if isinstance(stats_obj.get("event_control"), dict) else {}
        events = event_control.get("events") if isinstance(event_control.get("events"), list) else []
        return [event for event in events if isinstance(event, dict)]
    if artifact == "event_control_summary":
        event_control = stats_obj.get("event_control") if isinstance(stats_obj.get("event_control"), dict) else {}
        summary = event_control.get("summary") if isinstance(event_control.get("summary"), dict) else {}
        cache = event_control.get("cache") if isinstance(event_control.get("cache"), dict) else {}
        config = event_control.get("config") if isinstance(event_control.get("config"), dict) else {}
        return [
            {
                "status": event_control.get("status"),
                "reason": event_control.get("reason"),
                "total_articles_considered": summary.get("total_articles_considered"),
                "embedded_count": summary.get("embedded_count"),
                "event_count": summary.get("event_count"),
                "multi_source_event_count": summary.get("multi_source_event_count"),
                "singleton_count": summary.get("singleton_count"),
                "unavailable_reason": summary.get("unavailable_reason"),
                "cache_enabled": cache.get("enabled"),
                "cache_hits": cache.get("hits"),
                "cache_misses": cache.get("misses"),
                "cache_stored": cache.get("stored"),
                "embedding_model": config.get("embedding_model"),
                "embedding_dimensions": config.get("embedding_dimensions"),
                "similarity_threshold": config.get("similarity_threshold"),
                "date_window_days": config.get("date_window_days"),
            }
        ]
    if artifact == "event_source_coverage":
        event_control = stats_obj.get("event_control") if isinstance(stats_obj.get("event_control"), dict) else {}
        coverage = event_control.get("event_coverage") if isinstance(event_control.get("event_coverage"), dict) else {}
        rows = coverage.get("source_rows") if isinstance(coverage.get("source_rows"), list) else []
        return rows
    if artifact == "event_source_pair_coverage":
        event_control = stats_obj.get("event_control") if isinstance(stats_obj.get("event_control"), dict) else {}
        coverage = event_control.get("event_coverage") if isinstance(event_control.get("event_coverage"), dict) else {}
        rows = coverage.get("source_pair_rows") if isinstance(coverage.get("source_pair_rows"), list) else []
        return rows
    if artifact == "same_event_source_lens_effects":
        event_control = stats_obj.get("event_control") if isinstance(stats_obj.get("event_control"), dict) else {}
        effects = (
            event_control.get("same_event_source_lens_effects")
            if isinstance(event_control.get("same_event_source_lens_effects"), dict)
            else {}
        )
        rows = effects.get("rows") if isinstance(effects.get("rows"), list) else []
        return rows
    if artifact == "same_event_pairwise_source_lens_deltas":
        event_control = stats_obj.get("event_control") if isinstance(stats_obj.get("event_control"), dict) else {}
        deltas = (
            event_control.get("same_event_pairwise_source_lens_deltas")
            if isinstance(event_control.get("same_event_pairwise_source_lens_deltas"), dict)
            else {}
        )
        rows = deltas.get("rows") if isinstance(deltas.get("rows"), list) else []
        return rows
    if artifact == "same_event_variance_decomposition":
        event_control = stats_obj.get("event_control") if isinstance(stats_obj.get("event_control"), dict) else {}
        variance = (
            event_control.get("same_event_variance_decomposition")
            if isinstance(event_control.get("same_event_variance_decomposition"), dict)
            else {}
        )
        rows = variance.get("rows") if isinstance(variance.get("rows"), list) else []
        return rows
    if artifact == "same_event_source_differentiation_summary":
        event_control = stats_obj.get("event_control") if isinstance(stats_obj.get("event_control"), dict) else {}
        source_diff = (
            event_control.get("same_event_source_differentiation")
            if isinstance(event_control.get("same_event_source_differentiation"), dict)
            else {}
        )
        return _source_differentiation_summary_rows(source_diff)
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
        precomputed_error: PrecomputedStatsError | None = None

        try:
            snapshot_date_value = parse_snapshot_date(snapshot_date)
            if snapshot_date_value is None and stats_backend_mode() == "precomputed" and not force_refresh:
                try:
                    return _response_json(
                        200,
                        load_precomputed_stats_response(max_age_seconds=self.client.max_age_seconds),
                        headers=_read_cache_headers(
                            force_refresh=force_refresh,
                            snapshot_date=None,
                            seconds_env="NEWS_STATS_HTTP_CACHE_SECONDS",
                            default_seconds=300,
                        ),
                    )
                except PrecomputedStatsError as exc:
                    precomputed_error = exc
            bundle = self.client.get_payload(force_refresh=force_refresh, snapshot_date=snapshot_date_value)
        except ValueError as exc:
            return _response_json(400, {"status": "bad_request", "error": str(exc)})
        except RssDigestNotFoundError as exc:
            if snapshot_date_value:
                return _response_json(404, {"status": "not_found", "error": str(exc)})
            return _response_json(503, {"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"})
        except Exception as exc:  # noqa: BLE001
            return _response_json(503, {"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"})

        stats = bundle.get("stats") if isinstance(bundle.get("stats"), dict) else {}
        article_count = len(bundle.get("articles_normalized", []))
        meta = _common_meta(bundle, filtered_count=article_count, returned_count=article_count)
        headers = _read_cache_headers(
            force_refresh=force_refresh,
            snapshot_date=snapshot_date_value,
            seconds_env="NEWS_STATS_HTTP_CACHE_SECONDS",
            default_seconds=300,
        )
        if precomputed_error is not None:
            meta = _mark_precomputed_fallback(meta, precomputed_error)
            headers = _no_store_headers()
        return _response_json(
            200,
            {
                "status": "ok",
                "meta": meta,
                "data": {
                    "derived": stats,
                    "summary": bundle.get("summary", {}),
                    "analysis": bundle.get("analysis", {}),
                },
            },
            headers=headers,
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
        group_type: str | None = None,
        group_key: str | None = None,
        bucket_label: str | None = None,
    ) -> ControllerResponse:
        force_refresh = _parse_refresh(refresh)
        snapshot_date_value: str | None = None
        artifact_value = (artifact or "").strip()
        export_format_value = (export_format or "csv").strip().lower()
        precomputed_error: PrecomputedStatsError | None = None

        allowed_artifacts = {
            "event_clusters",
            "event_control_summary",
            "event_source_coverage",
            "event_source_pair_coverage",
            "group_temporal_buckets",
            "group_temporal_popularity_momentum",
            "group_temporal_path_summary",
            "source_tag_matrix",
            "source_score_status",
            "lens_pair_metrics",
            "same_event_source_differentiation_summary",
            "same_event_source_lens_effects",
            "same_event_pairwise_source_lens_deltas",
            "same_event_variance_decomposition",
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
            normalized_group_type, normalized_group_key, normalized_bucket_label = _normalize_group_temporal_bucket_filters(
                artifact_value,
                group_type,
                group_key,
                bucket_label,
            )
            snapshot_date_value = parse_snapshot_date(snapshot_date)
            if snapshot_date_value is None and stats_backend_mode() == "precomputed" and not force_refresh:
                try:
                    payload = load_precomputed_stats_response(max_age_seconds=self.client.max_age_seconds)
                except PrecomputedStatsError as exc:
                    precomputed_error = exc
                    payload = self.client.get_payload(force_refresh=force_refresh, snapshot_date=snapshot_date_value)
            else:
                payload = self.client.get_payload(force_refresh=force_refresh, snapshot_date=snapshot_date_value)
        except ValueError as exc:
            return _response_json(400, {"status": "bad_request", "error": str(exc)})
        except RssDigestNotFoundError as exc:
            if snapshot_date_value:
                return _response_json(404, {"status": "not_found", "error": str(exc)})
            return _response_json(503, {"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"})
        except Exception as exc:  # noqa: BLE001
            return _response_json(503, {"status": "upstream_error", "error": f"{type(exc).__name__}: {exc}"})

        rows = _export_rows_for_artifact(payload, artifact_value)
        rows = _filter_group_temporal_bucket_rows(
            rows,
            group_type=normalized_group_type,
            group_key=normalized_group_key,
            bucket_label=normalized_bucket_label,
        )
        meta = _export_meta_from_payload(payload, filtered_count=len(rows), returned_count=len(rows))
        headers = _read_cache_headers(force_refresh=force_refresh, snapshot_date=snapshot_date_value)
        if precomputed_error is not None:
            meta = _mark_precomputed_fallback(meta, precomputed_error)
            headers = _no_store_headers()
        filters = None
        if normalized_group_type or normalized_bucket_label:
            filters = {}
            if normalized_group_type:
                filters["group_type"] = normalized_group_type
                filters["group_key"] = normalized_group_key
            if normalized_bucket_label:
                filters["bucket_label"] = normalized_bucket_label

        if export_format_value == "json":
            return _response_json(
                200,
                {
                    "status": "ok",
                    "artifact": artifact_value,
                    "format": "json",
                    "meta": meta,
                    "filters": filters,
                    "rows": rows,
                },
                headers=headers,
            )

        csv_payload = _rows_to_csv(rows)
        return ControllerResponse(
            status_code=200,
            body=csv_payload,
            content_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{artifact_value}.csv"',
                **headers,
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
