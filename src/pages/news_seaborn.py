import base64
import hashlib
import io
import json
import os
import threading
import time
from typing import Any, Callable
from urllib.parse import urlencode

import dash
import dash_bootstrap_components as dbc
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from dash import Input, Output, callback, ctx, dcc, html
from flask import current_app


sns.set_theme(style="whitegrid")


dash.register_page(
    __name__,
    path="/news/seaborn",
    name="News Seaborn",
    title="Sentiment Analyzer | News Seaborn",
)


def _coerce_int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        parsed = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(parsed, minimum)


def _coerce_chart_format(name: str, default: str = "png") -> str:
    value = os.getenv(name, default).strip().lower()
    if value in {"png", "svg"}:
        return value
    return default


CHART_CACHE_VERSION = "1"
FIGURE_CACHE_TTL_SECONDS = _coerce_int_env("NEWS_FIGURE_CACHE_TTL_SECONDS", 21600)
FIGURE_CACHE_MAX_ITEMS = _coerce_int_env("NEWS_FIGURE_CACHE_MAX_ITEMS", 128)
FIGURE_OUTPUT_FORMAT = _coerce_chart_format("NEWS_FIGURE_OUTPUT_FORMAT", "png")
_FIGURE_CACHE_LOCK = threading.Lock()
_FIGURE_CACHE: dict[str, dict[str, Any]] = {}


def _api_get(path: str, params: dict[str, str | int | None]) -> tuple[int, dict]:
    filtered = {key: value for key, value in params.items() if value not in (None, "", [])}
    query = urlencode(filtered, doseq=True)
    target = f"{path}?{query}" if query else path
    with current_app.test_client() as client:
        response = client.get(target)
    parsed = response.get_json(silent=True)
    if isinstance(parsed, dict):
        return response.status_code, parsed
    return response.status_code, {"status": "error", "error": response.get_data(as_text=True)}


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]


def _to_data_url(figure) -> str:
    buffer = io.BytesIO()
    if FIGURE_OUTPUT_FORMAT == "svg":
        figure.savefig(buffer, format="svg", bbox_inches="tight")
        plt.close(figure)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"

    figure.savefig(buffer, format="png", dpi=140, bbox_inches="tight")
    plt.close(figure)
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _empty_chart(title: str, message: str) -> str:
    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.axis("off")
    axis.set_title(title)
    axis.text(0.5, 0.5, message, ha="center", va="center", fontsize=11)
    return _to_data_url(figure)


def _cache_prune(now_epoch: float) -> None:
    expired_keys = [
        key
        for key, payload in _FIGURE_CACHE.items()
        if payload.get("expires_at", 0.0) <= now_epoch
    ]
    for key in expired_keys:
        _FIGURE_CACHE.pop(key, None)

    if len(_FIGURE_CACHE) <= FIGURE_CACHE_MAX_ITEMS:
        return

    ordered = sorted(_FIGURE_CACHE.items(), key=lambda item: item[1].get("created_at", 0.0))
    for key, _ in ordered[: max(0, len(_FIGURE_CACHE) - FIGURE_CACHE_MAX_ITEMS)]:
        _FIGURE_CACHE.pop(key, None)


def _render_cached_figure(cache_key: str, render_fn: Callable[[], str]) -> tuple[str, bool]:
    now_epoch = time.time()
    with _FIGURE_CACHE_LOCK:
        _cache_prune(now_epoch)
        cached = _FIGURE_CACHE.get(cache_key)
        if cached and cached.get("expires_at", 0.0) > now_epoch:
            image_src = cached.get("image_src")
            if isinstance(image_src, str):
                return image_src, True

    image_src = render_fn()

    with _FIGURE_CACHE_LOCK:
        _cache_prune(now_epoch)
        _FIGURE_CACHE[cache_key] = {
            "image_src": image_src,
            "created_at": now_epoch,
            "expires_at": now_epoch + FIGURE_CACHE_TTL_SECONDS,
        }

    return image_src, False


def _chart_card(title: str, image_src: str, caption: str) -> dbc.Col:
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.H6(title, className="mb-2"),
                    html.Img(src=image_src, style={"width": "100%", "borderRadius": "0.25rem"}),
                    html.P(caption, className="text-muted small mt-2 mb-0"),
                ]
            ),
            className="shadow-sm h-100",
        ),
        lg=6,
        className="mb-3",
    )


def _source_count_chart(source_df: pd.DataFrame) -> str:
    if source_df.empty or "source" not in source_df or "count" not in source_df:
        return _empty_chart("Articles by Source", "No precomputed source count data.")
    data = source_df.head(12).copy()
    figure, axis = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=data, x="count", y="source", palette="Blues_r", ax=axis)
    axis.set_title("Articles by Source")
    axis.set_xlabel("Article count")
    axis.set_ylabel("")
    return _to_data_url(figure)


def _tag_count_chart(tag_df: pd.DataFrame) -> str:
    if tag_df.empty or "tag" not in tag_df or "count" not in tag_df:
        return _empty_chart("Top Tags", "No precomputed tag data.")
    data = tag_df.head(20).copy()
    figure, axis = plt.subplots(figsize=(8, 5))
    sns.barplot(data=data, x="count", y="tag", palette="Greens_r", ax=axis)
    axis.set_title("Top Tags")
    axis.set_xlabel("Tag count")
    axis.set_ylabel("")
    return _to_data_url(figure)


def _score_bin_chart(score_bin_df: pd.DataFrame) -> str:
    if score_bin_df.empty or "label" not in score_bin_df or "count" not in score_bin_df:
        return _empty_chart("Score Distribution", "No precomputed score-bin data.")
    figure, axis = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=score_bin_df, x="label", y="count", palette="Purples", ax=axis)
    axis.set_title("Score Distribution (%)")
    axis.set_xlabel("Score bin")
    axis.set_ylabel("Articles")
    return _to_data_url(figure)


def _daily_volume_chart(daily_df: pd.DataFrame) -> str:
    if daily_df.empty or "date" not in daily_df or "count" not in daily_df:
        return _empty_chart("Daily Volume", "No precomputed daily count data.")
    data = daily_df.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", utc=True)
    data = data.dropna(subset=["date"]).sort_values("date")
    if data.empty:
        return _empty_chart("Daily Volume", "Daily counts are not parseable as dates.")

    figure, axis = plt.subplots(figsize=(8, 4.5))
    sns.lineplot(data=data, x="date", y="count", marker="o", color="#ff7f0e", ax=axis)
    axis.set_title("Daily Article Volume (UTC)")
    axis.set_xlabel("UTC date")
    axis.set_ylabel("Articles")
    figure.autofmt_xdate()
    return _to_data_url(figure)


def _summary_metric_chart(summary_df: pd.DataFrame) -> str:
    if summary_df.empty:
        return _empty_chart("Contract Summary", "No upstream summary values.")
    figure, axis = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=summary_df, x="metric", y="value", palette="Set2", ax=axis)
    axis.set_title("Upstream Summary Metrics")
    axis.set_xlabel("")
    axis.set_ylabel("Value")
    axis.tick_params(axis="x", rotation=25)
    return _to_data_url(figure)


def _score_histogram_chart(hist_df: pd.DataFrame) -> str:
    if hist_df.empty or "label" not in hist_df or "count" not in hist_df:
        return _empty_chart("Score Histogram", "No precomputed score histogram bins.")
    figure, axis = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=hist_df, x="label", y="count", palette="deep", ax=axis)
    axis.set_title("Score Histogram (Precomputed Bins)")
    axis.set_xlabel("Score percent bin")
    axis.set_ylabel("Articles")
    axis.tick_params(axis="x", rotation=30)
    return _to_data_url(figure)


def _avg_score_source_chart(source_score_df: pd.DataFrame) -> str:
    if source_score_df.empty or "source" not in source_score_df or "avg_percent" not in source_score_df:
        return _empty_chart("Average Score by Source", "No precomputed source score summary.")
    data = source_score_df.dropna(subset=["avg_percent"]).sort_values("avg_percent", ascending=False).head(12)
    if data.empty:
        return _empty_chart("Average Score by Source", "No numeric average scores available.")
    figure, axis = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=data, x="avg_percent", y="source", palette="crest", ax=axis)
    axis.set_title("Average Score by Source")
    axis.set_xlabel("Average score percent")
    axis.set_ylabel("")
    return _to_data_url(figure)


def _publish_hour_chart(hour_df: pd.DataFrame) -> str:
    if hour_df.empty or "hour" not in hour_df or "count" not in hour_df:
        return _empty_chart("Publish Hour", "No precomputed publish-hour counts.")
    data = hour_df.sort_values("hour")
    figure, axis = plt.subplots(figsize=(8, 4.5))
    sns.lineplot(data=data, x="hour", y="count", marker="o", color="#e15759", ax=axis)
    axis.set_title("Article Publish Activity by UTC Hour")
    axis.set_xlabel("UTC hour")
    axis.set_ylabel("Articles")
    axis.set_xticks(list(range(0, 24, 2)))
    return _to_data_url(figure)


def _source_tag_heatmap(matrix_df: pd.DataFrame) -> str:
    required = {"source", "tag", "count"}
    if matrix_df.empty or not required.issubset(matrix_df.columns):
        return _empty_chart("Source vs Tag Heatmap", "No precomputed source/tag matrix data.")

    top_sources = matrix_df.groupby("source")["count"].sum().sort_values(ascending=False).head(8).index
    top_tags = matrix_df.groupby("tag")["count"].sum().sort_values(ascending=False).head(12).index
    data = matrix_df[matrix_df["source"].isin(top_sources) & matrix_df["tag"].isin(top_tags)]
    if data.empty:
        return _empty_chart("Source vs Tag Heatmap", "No overlapping high-frequency source/tag pairs.")

    pivot = data.pivot_table(index="source", columns="tag", values="count", aggfunc="sum", fill_value=0)
    figure, axis = plt.subplots(figsize=(10, 5.5))
    sns.heatmap(pivot, cmap="YlOrRd", linewidths=0.5, linecolor="white", ax=axis)
    axis.set_title("Source vs Tag Heatmap")
    axis.set_xlabel("Tag")
    axis.set_ylabel("Source")
    return _to_data_url(figure)


def _score_tag_heatmap(heatmap_df: pd.DataFrame) -> str:
    required = {"score_bin", "tag_count_bin", "count"}
    if heatmap_df.empty or not required.issubset(heatmap_df.columns):
        return _empty_chart("Score vs Tag Count", "No precomputed score/tag heatmap bins.")

    score_order = ["0-20", "20-40", "40-60", "60-80", "80-100"]
    tag_order = ["0", "1", "2", "3", "4+"]
    data = heatmap_df.copy()
    data["score_bin"] = pd.Categorical(data["score_bin"], categories=score_order, ordered=True)
    data["tag_count_bin"] = pd.Categorical(data["tag_count_bin"], categories=tag_order, ordered=True)

    pivot = data.pivot_table(
        index="tag_count_bin",
        columns="score_bin",
        values="count",
        aggfunc="sum",
        fill_value=0,
        observed=False,
    )
    figure, axis = plt.subplots(figsize=(8, 4.5))
    sns.heatmap(pivot, cmap="PuBuGn", linewidths=0.5, linecolor="white", annot=True, fmt="g", ax=axis)
    axis.set_title("Score Percent vs Tag Count (Precomputed Bins)")
    axis.set_xlabel("Score percent bin")
    axis.set_ylabel("Tag count bin")
    return _to_data_url(figure)


def _tag_count_distribution_chart(distribution_df: pd.DataFrame) -> str:
    if distribution_df.empty or "label" not in distribution_df or "count" not in distribution_df:
        return _empty_chart("Tag Count Distribution", "No precomputed tag-count distribution data.")
    order = ["0", "1", "2", "3", "4", "5+"]
    data = distribution_df.copy()
    data["label"] = pd.Categorical(data["label"], categories=order, ordered=True)
    data = data.sort_values("label")

    figure, axis = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=data, x="label", y="count", palette="rocket", ax=axis)
    axis.set_title("Tag Count Distribution per Article")
    axis.set_xlabel("Tags per article")
    axis.set_ylabel("Articles")
    return _to_data_url(figure)


def _high_score_source_chart(high_score_df: pd.DataFrame) -> str:
    if high_score_df.empty or "source" not in high_score_df or "count" not in high_score_df:
        return _empty_chart("High Scores by Source", "No precomputed high-score-by-source data.")
    data = high_score_df.head(12)
    figure, axis = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=data, x="count", y="source", palette="flare", ax=axis)
    axis.set_title("High Scoring Articles by Source")
    axis.set_xlabel("High-scoring articles")
    axis.set_ylabel("")
    return _to_data_url(figure)


def _lens_summary_chart(lens_df: pd.DataFrame) -> str:
    if lens_df.empty:
        return _empty_chart("Lens Summary", "No numeric lens-summary values in upstream analysis.")
    figure, axis = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=lens_df, x="lens", y="value", palette="magma", ax=axis)
    axis.set_title("Lens Summary (Upstream Analysis)")
    axis.set_xlabel("")
    axis.set_ylabel("Value")
    axis.tick_params(axis="x", rotation=30)
    return _to_data_url(figure)


def _chart_payloads(derived: dict, meta: dict) -> tuple[list[tuple[str, str, str]], int]:
    source_df = pd.DataFrame(derived.get("source_counts") or [])
    tag_df = pd.DataFrame(derived.get("tag_counts") or [])
    score_bin_df = pd.DataFrame((derived.get("score_distribution") or {}).get("bins") or [])
    daily_df = pd.DataFrame(derived.get("daily_counts_utc") or [])

    aggregates = derived.get("chart_aggregates") if isinstance(derived.get("chart_aggregates"), dict) else {}
    score_hist_df = pd.DataFrame(aggregates.get("score_histogram_bins") or [])
    source_score_df = pd.DataFrame(aggregates.get("source_score_summary") or [])
    publish_hour_df = pd.DataFrame(aggregates.get("publish_hour_counts_utc") or [])
    source_tag_df = pd.DataFrame(aggregates.get("source_tag_matrix") or [])
    score_tag_heatmap_df = pd.DataFrame(aggregates.get("score_tag_count_heatmap") or [])
    tag_count_distribution_df = pd.DataFrame(aggregates.get("tag_count_distribution") or [])
    high_score_source_df = pd.DataFrame(aggregates.get("high_score_by_source") or [])

    upstream_summary = derived.get("upstream_summary") if isinstance(derived.get("upstream_summary"), dict) else {}
    summary_rows = []
    for key in ("articles", "scored_articles", "high_scoring_articles"):
        value = upstream_summary.get(key)
        if isinstance(value, (int, float)):
            summary_rows.append({"metric": key, "value": value})
    summary_df = pd.DataFrame(summary_rows)

    lens_rows = []
    upstream_analysis = derived.get("upstream_analysis") if isinstance(derived.get("upstream_analysis"), dict) else {}
    lens_summary = upstream_analysis.get("lens_summary") if isinstance(upstream_analysis, dict) else None
    if isinstance(lens_summary, dict):
        for lens_name, lens_value in lens_summary.items():
            value = None
            if isinstance(lens_value, (int, float)):
                value = float(lens_value)
            elif isinstance(lens_value, dict):
                for candidate in ("average_percent", "avg_percent", "mean_percent", "avg_score", "score", "value"):
                    raw = lens_value.get(candidate)
                    if isinstance(raw, (int, float)):
                        value = float(raw)
                        break
            if value is not None:
                lens_rows.append({"lens": str(lens_name), "value": value})
    lens_df = pd.DataFrame(lens_rows)

    signature_payload = {
        "cache_version": CHART_CACHE_VERSION,
        "output_format": FIGURE_OUTPUT_FORMAT,
        "generated_at": meta.get("generated_at"),
        "digest_generated_at": meta.get("digest_generated_at"),
        "schema_version": meta.get("schema_version"),
        "contract": meta.get("contract"),
        "derived": derived,
    }
    signature = _stable_hash(signature_payload)

    chart_specs: list[tuple[str, str, Callable[[], str]]] = [
        ("Articles by Source", "Uses precomputed source_counts from /api/news/stats.", lambda: _source_count_chart(source_df)),
        ("Top Tags", "Uses precomputed tag_counts from /api/news/stats.", lambda: _tag_count_chart(tag_df)),
        ("Score Distribution Bins", "Uses precomputed score_distribution bins from /api/news/stats.", lambda: _score_bin_chart(score_bin_df)),
        ("Daily Volume (UTC)", "Uses precomputed daily_counts_utc from /api/news/stats.", lambda: _daily_volume_chart(daily_df)),
        ("Contract Summary Metrics", "Uses precomputed upstream summary values from the contract payload.", lambda: _summary_metric_chart(summary_df)),
        ("Score Histogram", "Uses precomputed chart_aggregates.score_histogram_bins.", lambda: _score_histogram_chart(score_hist_df)),
        ("Average Score by Source", "Uses precomputed chart_aggregates.source_score_summary.", lambda: _avg_score_source_chart(source_score_df)),
        ("Publish Hour Activity", "Uses precomputed chart_aggregates.publish_hour_counts_utc.", lambda: _publish_hour_chart(publish_hour_df)),
        ("Source vs Tag Heatmap", "Uses precomputed chart_aggregates.source_tag_matrix.", lambda: _source_tag_heatmap(source_tag_df)),
        ("Score vs Tag Count", "Uses precomputed chart_aggregates.score_tag_count_heatmap.", lambda: _score_tag_heatmap(score_tag_heatmap_df)),
        ("Tag Count Distribution", "Uses precomputed chart_aggregates.tag_count_distribution.", lambda: _tag_count_distribution_chart(tag_count_distribution_df)),
        ("High Scores by Source", "Uses precomputed chart_aggregates.high_score_by_source.", lambda: _high_score_source_chart(high_score_source_df)),
        ("Lens Summary", "Uses numeric values from precomputed analysis.lens_summary when available.", lambda: _lens_summary_chart(lens_df)),
    ]

    rendered: list[tuple[str, str, str]] = []
    cache_hits = 0
    for index, (title, caption, renderer) in enumerate(chart_specs):
        cache_key = f"{CHART_CACHE_VERSION}:{signature}:{index}"
        image_src, hit = _render_cached_figure(cache_key, renderer)
        if hit:
            cache_hits += 1
        rendered.append((title, image_src, caption))

    return rendered, cache_hits


layout = dbc.Container(
    [
        dcc.Interval(id="news-seaborn-load", interval=3000, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Seaborn Playground", className="mb-2"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    html.P(
                        "Charts built from precomputed /api/news/stats aggregates and cached rendered figures.",
                        className="text-muted mb-3",
                    ),
                    width=12,
                )
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        html.Div(
                            [
                                dbc.Button("Refresh", id="news-seaborn-refresh", color="secondary", className="me-2"),
                                dbc.Button("Refresh + Bypass Data Cache", id="news-seaborn-hard-refresh", color="primary"),
                            ]
                        ),
                    ],
                    md=6,
                ),
            ],
            className="mb-3",
        ),
        dbc.Row([dbc.Col(html.Div(id="news-seaborn-status"), width=12)]),
        dbc.Row(id="news-seaborn-charts"),
        dbc.Row([dbc.Col(html.Pre(id="news-seaborn-debug", className="small mb-0"), width=12)]),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-seaborn-status", "children"),
    Output("news-seaborn-charts", "children"),
    Output("news-seaborn-debug", "children"),
    Input("news-seaborn-load", "n_intervals"),
    Input("news-seaborn-refresh", "n_clicks"),
    Input("news-seaborn-hard-refresh", "n_clicks"),
)
def load_news_seaborn(_load_tick, _refresh_clicks, _hard_refresh_clicks):
    force_refresh = ctx.triggered_id == "news-seaborn-hard-refresh"
    params = {"refresh": "true" if force_refresh else None}

    stats_status, stats_payload = _api_get("/api/news/stats", params)
    if stats_status != 200:
        error_message = {
            "stats_status_code": stats_status,
            "stats_error": stats_payload.get("error"),
        }
        return (
            dbc.Alert("Failed to load precomputed news stats for Seaborn charts.", color="danger", className="mb-3"),
            [],
            json.dumps(error_message, indent=2, default=str),
        )

    stats_data = stats_payload.get("data", {}) if isinstance(stats_payload.get("data"), dict) else {}
    derived = stats_data.get("derived", {}) if isinstance(stats_data.get("derived"), dict) else {}
    meta = stats_payload.get("meta", {}) if isinstance(stats_payload.get("meta"), dict) else {}

    chart_models, cache_hits = _chart_payloads(derived, meta)
    chart_cards = [_chart_card(title, image_src, caption) for title, image_src, caption in chart_models]

    status_line = (
        f"Charts: {len(chart_models)} | "
        f"Generated at: {meta.get('generated_at')} | "
        f"Data cache: {'hit' if meta.get('from_cache') else 'miss'} | "
        f"Figure cache hits: {cache_hits}/{len(chart_models)} | "
        f"Format: {FIGURE_OUTPUT_FORMAT.upper()}"
    )
    if meta.get("using_last_good"):
        status_line += " | using last-good fallback"
    status_component = dbc.Alert(status_line, color="info", className="mb-3")

    with _FIGURE_CACHE_LOCK:
        cache_size = len(_FIGURE_CACHE)

    debug_payload = {
        "stats_status": stats_payload.get("status"),
        "total_articles_precomputed": derived.get("total_articles"),
        "schema_version": meta.get("schema_version"),
        "contract": meta.get("contract"),
        "cache_ttl_seconds": FIGURE_CACHE_TTL_SECONDS,
        "cache_max_items": FIGURE_CACHE_MAX_ITEMS,
        "figure_output_format": FIGURE_OUTPUT_FORMAT,
        "cache_entries": cache_size,
        "chart_cache_hits": cache_hits,
        "chart_count": len(chart_models),
        "has_chart_aggregates": isinstance(derived.get("chart_aggregates"), dict),
    }

    return status_component, chart_cards, json.dumps(debug_payload, indent=2, default=str)
