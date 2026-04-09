from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from flask import jsonify, make_response, request

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
    if artifact == "source_score_summary":
        rows = chart_aggregates.get("source_score_summary")
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

    @server.get("/api/news/export")
    def export_news_artifact():
        force_refresh = request.args.get("refresh", "").strip().lower() in {"1", "true", "yes"}
        snapshot_date: str | None = None
        artifact = (request.args.get("artifact") or "").strip()
        export_format = (request.args.get("format") or "csv").strip().lower()

        allowed_artifacts = {
            "source_tag_matrix",
            "source_score_summary",
            "lens_pair_metrics",
            "source_lens_effects",
            "source_differentiation_summary",
        }
        if artifact not in allowed_artifacts:
            return (
                jsonify(
                    {
                        "status": "bad_request",
                        "error": f"artifact must be one of {sorted(allowed_artifacts)}",
                    }
                ),
                400,
            )

        if export_format not in {"csv", "json"}:
            return jsonify({"status": "bad_request", "error": "format must be csv or json"}), 400

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

        rows = _export_rows_for_artifact(bundle, artifact)
        meta = _common_meta(bundle, filtered_count=len(rows), returned_count=len(rows))

        if export_format == "json":
            return (
                jsonify(
                    {
                        "status": "ok",
                        "artifact": artifact,
                        "format": "json",
                        "meta": meta,
                        "rows": rows,
                    }
                ),
                200,
            )

        csv_payload = _rows_to_csv(rows)
        response = make_response(csv_payload)
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = f'attachment; filename="{artifact}.csv"'
        return response, 200

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
