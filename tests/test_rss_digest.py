import json
import os
import tempfile
import unittest
from pathlib import Path

from src.services.rss_digest import (
    DEFAULT_RSS_DAILY_JSON_URL,
    DEFAULT_RSS_HISTORY_JSON_URL_TEMPLATE,
    RssDigestClient,
    derive_stats,
    filter_records,
    normalize_articles,
    parse_datetime,
    sort_records_desc,
)


SAMPLE_PAYLOAD = {
    "schema_version": "1.0",
    "generated_at": "2026-03-02T20:54:00Z",
    "contract": "rss_pipeline_precomputed",
    "summary": {"articles": 3, "scored_articles": 3},
    "analysis": {"lens_summary": {}, "source_differentiation": {}},
    "articles": [
        {
            "id": "a-1",
            "title": "Latest Story",
            "link": "https://example.com/latest",
            "published": "Mon, 02 Mar 2026 15:25:29 -0500",
            "summary": "Summary 1",
            "ai_summary": "AI Summary 1",
            "ai_tags": ["OpenAI", "Policy"],
            "topic_tags": ["General"],
            "source": {"id": "pbs-newshour", "name": "PBS NewsHour"},
            "feed": {"name": "Headlines", "url": "https://example.com/feed"},
            "scraped": {"title": "Latest Story", "body_text": "Body"},
            "scrape_error": None,
            "score": {
                "value": 14.0,
                "max_value": 20.0,
                "percent": 70.0,
                "rubric_count": 3,
                "lens_scores": {"L1": {"percent": 70.0}},
            },
        },
        {
            "id": "a-2",
            "title": "Older Story",
            "link": "https://example.com/older",
            "published": "2026-03-01T03:10:00Z",
            "summary": "Summary 2",
            "ai_summary": "AI Summary 2",
            "ai_tags": ["Science"],
            "topic_tags": ["OpenAI"],
            "source": {"id": "npr", "name": "NPR"},
            "feed": {"name": "World", "url": "https://example.com/world"},
            "scraped": {"title": "Older Story", "body_text": "Body"},
            "scrape_error": None,
            "score": {"value": 8.0, "max_value": 20.0, "percent": 40.0, "rubric_count": 3},
        },
        {
            "id": "a-3",
            "title": "Failed Scrape Story",
            "link": "https://example.com/failed",
            "published": "2026-03-03T04:00:00Z",
            "summary": "Summary 3",
            "ai_summary": "AI Summary 3",
            "ai_tags": ["OpenAI"],
            "topic_tags": ["General"],
            "source": {"id": "failed-source", "name": "Failed Source"},
            "feed": {"name": "Errors", "url": "https://example.com/errors"},
            "scraped": None,
            "scrape_error": "HTTP 403",
            "score": {"value": 20.0, "max_value": 20.0, "percent": 100.0, "rubric_count": 3},
        },
    ],
}


class RssDigestServiceTests(unittest.TestCase):
    def test_placeholder_env_urls_fall_back_to_defaults(self):
        previous_current = os.environ.get("RSS_DAILY_JSON_URL")
        previous_history = os.environ.get("RSS_HISTORY_JSON_URL_TEMPLATE")
        try:
            os.environ["RSS_DAILY_JSON_URL"] = "-"
            os.environ["RSS_HISTORY_JSON_URL_TEMPLATE"] = "-"
            client = RssDigestClient()
            self.assertEqual(client.current_source_url, DEFAULT_RSS_DAILY_JSON_URL)
            self.assertEqual(client.history_url_template, DEFAULT_RSS_HISTORY_JSON_URL_TEMPLATE)
        finally:
            if previous_current is None:
                os.environ.pop("RSS_DAILY_JSON_URL", None)
            else:
                os.environ["RSS_DAILY_JSON_URL"] = previous_current

            if previous_history is None:
                os.environ.pop("RSS_HISTORY_JSON_URL_TEMPLATE", None)
            else:
                os.environ["RSS_HISTORY_JSON_URL_TEMPLATE"] = previous_history

    def test_parse_datetime_supports_rfc2822(self):
        parsed = parse_datetime("Mon, 02 Mar 2026 15:25:29 -0500")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.isoformat().replace("+00:00", "Z"), "2026-03-02T20:25:29Z")

    def test_normalize_and_filter_semantics(self):
        records = normalize_articles(SAMPLE_PAYLOAD)
        self.assertEqual(len(records), 2)
        self.assertNotIn("a-3", [record["id"] for record in records])
        self.assertEqual(records[0]["source"]["name"], "PBS NewsHour")
        self.assertIn("OpenAI", records[0]["tags"])

        by_date = filter_records(records, date_filter="2026-03-02")
        self.assertEqual(len(by_date), 1)
        self.assertEqual(by_date[0]["id"], "a-1")

        by_tag = filter_records(records, tag_filter="openai")
        self.assertEqual(len(by_tag), 2)

        by_source = filter_records(records, source_filter="pbs")
        self.assertEqual(len(by_source), 1)
        self.assertEqual(by_source[0]["id"], "a-1")

    def test_date_filter_uses_utc(self):
        payload = {
            "articles": [
                {
                    "id": "tz-1",
                    "title": "TZ case",
                    "published": "Sun, 01 Mar 2026 23:30:00 -0500",
                    "ai_tags": ["OpenAI"],
                    "topic_tags": [],
                    "source": {"id": "tz-source", "name": "TZ Source"},
                    "feed": {"name": "TZ Feed", "url": "https://example.com/tz"},
                    "score": {"value": 1, "max_value": 1, "percent": 100, "rubric_count": 1},
                }
            ]
        }
        records = normalize_articles(payload)
        matched = filter_records(records, date_filter="2026-03-02")
        self.assertEqual(len(matched), 1)

    def test_sort_and_stats(self):
        records = normalize_articles(SAMPLE_PAYLOAD)
        ordered = sort_records_desc(records)
        self.assertEqual(ordered[0]["id"], "a-1")

        stats = derive_stats(ordered, SAMPLE_PAYLOAD)
        self.assertEqual(stats["input_articles"], 3)
        self.assertEqual(stats["excluded_unscraped_articles"], 1)
        self.assertEqual(stats["total_articles"], 2)
        self.assertEqual(stats["scored_articles"], 1)
        self.assertEqual(stats["zero_score_articles"], 0)
        self.assertEqual(stats["positive_score_articles"], 1)
        self.assertEqual(stats["unscorable_articles"], 1)
        self.assertEqual(stats["score_object_present_articles"], 2)
        self.assertEqual(stats["score_object_missing_articles"], 0)
        self.assertEqual(stats["placeholder_zero_unscorable_articles"], 0)
        self.assertIn("score_status", stats)
        self.assertEqual(stats["score_status"]["scored"], 1)
        self.assertEqual(stats["score_status"]["unscorable"], 1)
        self.assertEqual(stats["score_coverage_ratio"], 0.5)
        self.assertTrue(stats["source_counts"])
        self.assertTrue(stats["tag_counts"])

        chart_aggregates = stats["chart_aggregates"]
        self.assertIn("tag_count_distribution", chart_aggregates)
        self.assertIn("publish_hour_counts_utc", chart_aggregates)
        self.assertIn("source_tag_matrix", chart_aggregates)
        self.assertIn("source_tag_totals", chart_aggregates)
        self.assertIn("tag_totals", chart_aggregates)
        self.assertIn("scored_by_source", chart_aggregates)
        self.assertIn("score_status_by_source", chart_aggregates)
        self.assertIn("source_tag_views", stats)

        self.assertEqual(len(chart_aggregates["tag_count_distribution"]), 6)
        self.assertEqual(len(chart_aggregates["publish_hour_counts_utc"]), 24)
        self.assertEqual(chart_aggregates["source_tag_totals"][0]["source"], "PBS NewsHour")
        self.assertEqual(chart_aggregates["source_tag_totals"][0]["count"], 3)
        self.assertEqual(chart_aggregates["source_tag_totals"][1]["source"], "NPR")
        self.assertEqual(chart_aggregates["source_tag_totals"][1]["count"], 2)
        self.assertEqual(chart_aggregates["tag_totals"][0]["tag"], "OpenAI")
        self.assertEqual(chart_aggregates["tag_totals"][0]["count"], 2)
        source_tag_views = stats["source_tag_views"]
        self.assertIn("source_labels", source_tag_views)
        self.assertIn("tag_labels", source_tag_views)
        self.assertIn("source_rows", source_tag_views)
        self.assertIn("summary", source_tag_views)
        self.assertEqual(source_tag_views["source_labels"][0], "PBS NewsHour")
        self.assertEqual(source_tag_views["tag_labels"][0], "OpenAI")
        self.assertEqual(source_tag_views["source_rows"][0]["source"], "PBS NewsHour")
        self.assertEqual(source_tag_views["source_rows"][0]["count"], 3)
        self.assertEqual(source_tag_views["summary"]["source_count"], 2)
        self.assertEqual(source_tag_views["summary"]["tag_count"], 4)
        self.assertEqual(source_tag_views["summary"]["matrix_rows"], 5)
        self.assertEqual(source_tag_views["summary"]["non_zero_cells"], 5)
        self.assertEqual(source_tag_views["summary"]["total_assignments"], 5)

        self.assertEqual(
            sum(item["count"] for item in chart_aggregates["tag_count_distribution"]),
            stats["total_articles"],
        )

        lens_correlations = stats["lens_correlations"]
        self.assertIn("lenses", lens_correlations)
        self.assertIn("correlation", lens_correlations)
        self.assertIn("covariance", lens_correlations)
        self.assertIn("pairwise_counts", lens_correlations)
        self.assertIn("pair_rankings", lens_correlations)
        self.assertIn("summary_by_matrix", lens_correlations)
        self.assertIn("source_differentiation", stats)
        self.assertIn("status", stats["source_differentiation"])
        self.assertIn("source_counts", stats["source_differentiation"])
        self.assertIn("multivariate", stats["source_differentiation"])
        self.assertIn("classification", stats["source_differentiation"])
        self.assertIn("source_lens_effects", stats)
        self.assertIn("status", stats["source_lens_effects"])
        self.assertIn("permutations", stats["source_lens_effects"])
        self.assertIn("multiple_testing", stats["source_lens_effects"])
        self.assertIn("rows", stats["source_lens_effects"])
        self.assertIn("source_topic_control", stats)
        source_topic_control = stats["source_topic_control"]
        self.assertEqual(source_topic_control["topic_basis"], "topic_tags")
        self.assertEqual(source_topic_control["multi_topic_policy"], "duplicate_per_topic")
        self.assertEqual(source_topic_control["pooled_label"], "topic-confounded")
        self.assertIn("pooled", source_topic_control)
        self.assertIn("topics", source_topic_control)
        self.assertIn("summary", source_topic_control)
        self.assertEqual(
            source_topic_control["pooled"]["source_differentiation"],
            stats["source_differentiation"],
        )
        self.assertEqual(
            source_topic_control["pooled"]["source_lens_effects"],
            stats["source_lens_effects"],
        )
        self.assertIn("tag_sliced_analysis", stats)
        tag_sliced_analysis = stats["tag_sliced_analysis"]
        self.assertEqual(tag_sliced_analysis["tag_basis"], "topic_tags")
        self.assertEqual(tag_sliced_analysis["multi_tag_policy"], "duplicate_per_tag")
        self.assertEqual(tag_sliced_analysis["pooled_label"], "tag-confounded")
        self.assertIn("pooled", tag_sliced_analysis)
        self.assertIn("tags", tag_sliced_analysis)
        self.assertIn("summary", tag_sliced_analysis)
        self.assertEqual(
            tag_sliced_analysis["pooled"]["source_differentiation"],
            stats["source_differentiation"],
        )
        self.assertEqual(
            tag_sliced_analysis["pooled"]["source_lens_effects"],
            stats["source_lens_effects"],
        )
        self.assertIn("event_control", stats)
        event_control = stats["event_control"]
        self.assertIn(event_control["status"], {"ok", "unavailable"})
        self.assertIn("config", event_control)
        self.assertIn("summary", event_control)
        self.assertIn("events", event_control)
        self.assertIn("same_event_source_differentiation", event_control)
        self.assertIn("same_event_source_lens_effects", event_control)
        self.assertIn("same_event_pairwise_source_lens_deltas", event_control)
        self.assertIn("event_coverage", event_control)
        self.assertIn("same_event_variance_decomposition", event_control)
        self.assertIn("source_reliability", stats)
        source_reliability = stats["source_reliability"]
        self.assertEqual(source_reliability["method"], "heuristic-v1")
        self.assertEqual(source_reliability["pooled_label"], "topic-confounded")
        self.assertIn("pooled", source_reliability)
        self.assertIn("topics", source_reliability)
        self.assertIn("summary", source_reliability)
        self.assertIn(source_reliability["pooled"].get("status"), {"ok", "unavailable"})
        self.assertIn(
            source_reliability["pooled"].get("tier"),
            {"high", "moderate", "low", "unavailable"},
        )
        self.assertIn("flags", source_reliability["pooled"])
        self.assertIn("metrics", source_reliability["pooled"])
        self.assertIn("lens_pca", stats)
        lens_pca = stats["lens_pca"]
        self.assertIn("status", lens_pca)
        self.assertIn("reason", lens_pca)
        self.assertIn("components", lens_pca)
        self.assertIn("explained_variance", lens_pca)
        self.assertIn("variance_drivers", lens_pca)
        self.assertIn("article_points", lens_pca)
        self.assertIn("source_centroids", lens_pca)
        self.assertEqual(lens_pca["status"], "unavailable")
        self.assertIn("lens_mds", stats)
        lens_mds = stats["lens_mds"]
        self.assertIn("status", lens_mds)
        self.assertIn("reason", lens_mds)
        self.assertIn("dimensions", lens_mds)
        self.assertIn("dimension_strength", lens_mds)
        self.assertIn("stress", lens_mds)
        self.assertIn("article_points", lens_mds)
        self.assertIn("source_centroids", lens_mds)
        self.assertEqual(lens_mds["status"], "unavailable")
        self.assertIn("lens_time_series", stats)
        lens_time_series = stats["lens_time_series"]
        self.assertIn("status", lens_time_series)
        self.assertIn("reason", lens_time_series)
        self.assertIn("lenses", lens_time_series)
        self.assertIn("dates", lens_time_series)
        self.assertIn("series", lens_time_series)
        self.assertIn("summary", lens_time_series)
        self.assertIn("lens_temporal_embedding", stats)
        lens_temporal_embedding = stats["lens_temporal_embedding"]
        self.assertIn("status", lens_temporal_embedding)
        self.assertIn("reason", lens_temporal_embedding)
        self.assertIn("points", lens_temporal_embedding)
        self.assertIn("day_centroids", lens_temporal_embedding)
        self.assertIn("summary", lens_temporal_embedding)
        self.assertIn("lens_temporal_embedding_mds", stats)
        lens_temporal_embedding_mds = stats["lens_temporal_embedding_mds"]
        self.assertIn("status", lens_temporal_embedding_mds)
        self.assertIn("reason", lens_temporal_embedding_mds)
        self.assertIn("points", lens_temporal_embedding_mds)
        self.assertIn("day_centroids", lens_temporal_embedding_mds)
        self.assertIn("summary", lens_temporal_embedding_mds)
        self.assertIn("lens_views", stats)
        lens_views = stats["lens_views"]
        self.assertIn("coverage_mode", lens_views)
        self.assertIn("lens_names", lens_views)
        self.assertIn("article_rows", lens_views)
        self.assertIn("source_rows", lens_views)
        self.assertIn("stability_rows", lens_views)
        self.assertIn("summary", lens_views)
        self.assertIsInstance(lens_views["lens_names"], list)
        self.assertIsInstance(lens_views["article_rows"], list)
        self.assertIsInstance(lens_views["source_rows"], list)
        self.assertIsInstance(lens_views["stability_rows"], list)
        self.assertIsInstance(lens_views["summary"], dict)
        self.assertEqual(lens_views["summary"]["article_count"], 1)
        self.assertIsInstance(lens_views["summary"]["dominant_lens_counts"], list)
        self.assertEqual(lens_views["summary"]["dominant_lens_counts"][0]["lens"], "L1")
        self.assertEqual(lens_views["summary"]["dominant_lens_counts"][0]["count"], 1)
        self.assertIsInstance(lens_views["summary"]["lens_average_rows"], list)
        self.assertEqual(lens_views["summary"]["lens_average_rows"][0]["lens"], "L1")
        self.assertEqual(lens_views["summary"]["lens_average_rows"][0]["count"], 1)
        self.assertEqual(lens_views["summary"]["lens_average_rows"][0]["mean"], 70.0)
        self.assertEqual(lens_views["summary"]["source_count"], 1)
        self.assertEqual(lens_views["summary"]["covered_articles"], 1)
        self.assertIsInstance(lens_views["summary"]["source_lens_average_rows"], list)
        self.assertEqual(lens_views["summary"]["source_lens_average_rows"][0]["lens"], "L1")
        self.assertEqual(lens_views["summary"]["source_lens_average_rows"][0]["count"], 1)
        self.assertEqual(lens_views["summary"]["source_lens_average_rows"][0]["mean"], 70.0)
        self.assertEqual(lens_views["summary"]["stability_lens_count"], 1)
        self.assertEqual(lens_views["summary"]["stability_avg_stddev"], 0.0)
        self.assertEqual(lens_views["summary"]["stability_top_lens"], "L1")
        self.assertEqual(lens_views["summary"]["stability_total_samples"], 1)
        self.assertIn("lens_inventory", stats)
        lens_inventory = stats["lens_inventory"]
        self.assertIn("coverage_mode", lens_inventory)
        self.assertIn("items_total", lens_inventory)
        self.assertIn("aggregation", lens_inventory)
        self.assertIn("lenses", lens_inventory)
        self.assertIsInstance(lens_inventory["lenses"], list)
        self.assertIn("data_quality", stats)
        data_quality = stats["data_quality"]
        self.assertIn("summary", data_quality)
        self.assertIn("field_coverage", data_quality)
        self.assertIsInstance(data_quality["field_coverage"], list)
        self.assertEqual(data_quality["summary"]["total"], 2)
        self.assertEqual(data_quality["summary"]["scored"], 1)
        self.assertEqual(data_quality["summary"]["missing_ai_summary"], 0)
        self.assertEqual(data_quality["summary"]["missing_published"], 0)
        self.assertEqual(data_quality["summary"]["missing_source"], 0)
        self.assertAlmostEqual(float(data_quality["summary"]["average_tags"]), 2.5, places=6)
        coverage_by_field = {row["field"]: row for row in data_quality["field_coverage"]}
        self.assertEqual(coverage_by_field["Title"]["present"], 2)
        self.assertEqual(coverage_by_field["Lens Scores"]["present"], 1)

        lenses = lens_correlations["lenses"]
        pairwise = lens_correlations["pairwise_counts"]
        corr_raw = lens_correlations["correlation"]["raw"]
        cov_raw = lens_correlations["covariance"]["raw"]
        pair_rankings = lens_correlations["pair_rankings"]
        summary_by_matrix = lens_correlations["summary_by_matrix"]
        self.assertEqual(len(pairwise), len(lenses))
        self.assertEqual(len(corr_raw), len(lenses))
        self.assertEqual(len(cov_raw), len(lenses))
        self.assertEqual(sorted(pair_rankings.keys()), ["corr_norm", "corr_raw", "cov_norm", "cov_raw", "pairwise"])
        self.assertEqual(sorted(summary_by_matrix.keys()), ["corr_norm", "corr_raw", "cov_norm", "cov_raw", "pairwise"])
        self.assertEqual(summary_by_matrix["corr_raw"]["lens_count"], len(lenses))
        self.assertEqual(summary_by_matrix["corr_raw"]["pair_count"], 0)
        self.assertIsNone(summary_by_matrix["corr_raw"]["strongest_pair"])
        self.assertIsNone(summary_by_matrix["corr_raw"]["strongest_value"])
        if lenses:
            self.assertEqual(pairwise[0][0], 1)

    def test_lens_pca_is_derived_when_complete_rows_exist(self):
        payload = {
            "analysis": {
                "lens_summary": {
                    "lenses": [
                        {"name": "Evidence", "max_total": 10.0},
                        {"name": "Impact", "max_total": 10.0},
                        {"name": "Novelty", "max_total": 10.0},
                    ]
                }
            },
            "articles": [
                {
                    "id": "pca-1",
                    "title": "PCA one",
                    "published": "2026-03-02T00:00:00Z",
                    "ai_tags": ["OpenAI"],
                    "topic_tags": [],
                    "source": {"name": "Source A"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "PCA one", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {
                        "value": 8.0,
                        "max_value": 10.0,
                        "percent": 80.0,
                        "lens_scores": {
                            "Evidence": {"percent": 90.0},
                            "Impact": {"percent": 70.0},
                            "Novelty": {"percent": 60.0},
                        },
                    },
                },
                {
                    "id": "pca-2",
                    "title": "PCA two",
                    "published": "2026-03-02T01:00:00Z",
                    "ai_tags": ["OpenAI"],
                    "topic_tags": [],
                    "source": {"name": "Source A"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "PCA two", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {
                        "value": 6.0,
                        "max_value": 10.0,
                        "percent": 60.0,
                        "lens_scores": {
                            "Evidence": {"percent": 80.0},
                            "Impact": {"percent": 50.0},
                            "Novelty": {"percent": 45.0},
                        },
                    },
                },
                {
                    "id": "pca-3",
                    "title": "PCA three",
                    "published": "2026-03-02T02:00:00Z",
                    "ai_tags": ["OpenAI"],
                    "topic_tags": [],
                    "source": {"name": "Source B"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "PCA three", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {
                        "value": 9.0,
                        "max_value": 10.0,
                        "percent": 90.0,
                        "lens_scores": {
                            "Evidence": {"percent": 40.0},
                            "Impact": {"percent": 85.0},
                            "Novelty": {"percent": 75.0},
                        },
                    },
                },
                {
                    "id": "pca-4",
                    "title": "PCA four",
                    "published": "2026-03-02T03:00:00Z",
                    "ai_tags": ["OpenAI"],
                    "topic_tags": [],
                    "source": {"name": "Source B"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "PCA four", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {
                        "value": 7.0,
                        "max_value": 10.0,
                        "percent": 70.0,
                        "lens_scores": {
                            "Evidence": {"percent": 35.0},
                            "Impact": {"percent": 78.0},
                            "Novelty": {"percent": 65.0},
                        },
                    },
                },
            ],
        }

        records = normalize_articles(payload)
        stats = derive_stats(sort_records_desc(records), payload)
        pca = stats["lens_pca"]
        if pca["status"] == "unavailable":
            self.assertIn("numpy", str(pca.get("reason", "")).lower())
            self.assertEqual(pca["n_articles"], 0)
            self.assertEqual(pca["components"], [])
            return

        self.assertEqual(pca["status"], "ok")
        self.assertEqual(pca["n_articles"], 4)
        self.assertEqual(pca["n_lenses"], 3)
        self.assertEqual(len(pca["components"]), 3)
        self.assertEqual(len(pca["explained_variance"]), 3)
        self.assertEqual(pca["coverage_mode"], "complete_rows")
        self.assertGreater(len(pca["variance_drivers"]), 0)
        self.assertEqual(len(pca["article_points"]), 4)
        self.assertEqual(len(pca["source_centroids"]), 2)

        loadings = pca["loadings"]
        self.assertEqual(loadings["lenses"], pca["lenses"])
        self.assertEqual(loadings["components"], pca["components"])
        self.assertEqual(len(loadings["matrix"]), 3)
        self.assertEqual(len(loadings["matrix"][0]), 3)

        mds = stats["lens_mds"]
        self.assertEqual(mds["status"], "ok")
        self.assertEqual(mds["n_articles"], 4)
        self.assertEqual(mds["n_lenses"], 3)
        self.assertEqual(mds["dimensions"], ["MDS1", "MDS2", "MDS3"])
        self.assertEqual(mds["coverage_mode"], "complete_rows")
        self.assertEqual(len(mds["dimension_strength"]), 3)
        self.assertEqual(len(mds["article_points"]), 4)
        self.assertEqual(len(mds["source_centroids"]), 2)
        self.assertIsInstance(mds["stress"], float)

        separation = stats["lens_separation"]
        self.assertEqual(separation["status"], "ok")
        self.assertEqual(separation["n_articles"], 4)
        self.assertEqual(separation["n_lenses"], 3)
        self.assertEqual(separation["n_sources"], 2)
        self.assertEqual(separation["coverage_mode"], "complete_rows")
        self.assertIsInstance(separation["source_centroids"], list)
        self.assertIsInstance(separation["centroid_distances"], list)

    def test_score_status_distinguishes_zero_from_unscorable(self):
        payload = {
            "articles": [
                {
                    "id": "score-zero",
                    "title": "Scored zero",
                    "published": "2026-03-02T00:00:00Z",
                    "ai_tags": ["A"],
                    "topic_tags": [],
                    "source": {"name": "Source A"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "Scored zero", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"L1": {"percent": 0.0}}},
                },
                {
                    "id": "placeholder-zero",
                    "title": "Placeholder zero",
                    "published": "2026-03-02T01:00:00Z",
                    "ai_tags": ["B"],
                    "topic_tags": [],
                    "source": {"name": "Source B"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "Placeholder zero", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"value": None, "max_value": 0.0, "percent": 0.0},
                },
                {
                    "id": "missing-score",
                    "title": "Missing score",
                    "published": "2026-03-02T02:00:00Z",
                    "ai_tags": ["C"],
                    "topic_tags": [],
                    "source": {"name": "Source C"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "Missing score", "body_text": "Body"},
                    "scrape_error": None,
                    "score": None,
                },
            ]
        }

        records = normalize_articles(payload)
        stats = derive_stats(sort_records_desc(records), payload)
        self.assertEqual(stats["total_articles"], 3)
        self.assertEqual(stats["scored_articles"], 1)
        self.assertEqual(stats["zero_score_articles"], 1)
        self.assertEqual(stats["positive_score_articles"], 0)
        self.assertEqual(stats["unscorable_articles"], 2)
        self.assertEqual(stats["placeholder_zero_unscorable_articles"], 1)
        self.assertAlmostEqual(stats["score_coverage_ratio"], 1 / 3, places=6)
        self.assertEqual(stats["score_status"]["zero"], 1)
        self.assertEqual(stats["score_status"]["unscorable"], 2)
        self.assertEqual(stats["score_status"]["placeholder_zero_unscorable"], 1)
        self.assertEqual(stats["data_quality"]["summary"]["scored"], 1)

    def test_source_lens_effects_are_derived_when_source_signal_exists(self):
        payload = {
            "analysis": {"lens_summary": {"lenses": [{"name": "Evidence", "max_total": 10.0}]}},
            "articles": [
                {
                    "id": "s-a-1",
                    "title": "A1",
                    "published": "2026-03-02T00:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": [],
                    "source": {"name": "Source A"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "A1", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 90.0}}},
                },
                {
                    "id": "s-a-2",
                    "title": "A2",
                    "published": "2026-03-02T01:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": [],
                    "source": {"name": "Source A"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "A2", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 88.0}}},
                },
                {
                    "id": "s-a-3",
                    "title": "A3",
                    "published": "2026-03-02T02:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": [],
                    "source": {"name": "Source A"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "A3", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 91.0}}},
                },
                {
                    "id": "s-b-1",
                    "title": "B1",
                    "published": "2026-03-02T03:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": [],
                    "source": {"name": "Source B"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "B1", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 20.0}}},
                },
                {
                    "id": "s-b-2",
                    "title": "B2",
                    "published": "2026-03-02T04:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": [],
                    "source": {"name": "Source B"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "B2", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 18.0}}},
                },
                {
                    "id": "s-b-3",
                    "title": "B3",
                    "published": "2026-03-02T05:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": [],
                    "source": {"name": "Source B"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "B3", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 22.0}}},
                },
            ],
        }
        records = normalize_articles(payload)
        stats = derive_stats(sort_records_desc(records), payload)
        effects = stats["source_lens_effects"]
        self.assertEqual(effects["status"], "ok")
        self.assertGreaterEqual(effects["permutations"], 1)
        rows = effects["rows"]
        self.assertGreaterEqual(len(rows), 1)
        evidence_row = next((row for row in rows if row.get("lens") == "Evidence"), None)
        self.assertIsNotNone(evidence_row)
        self.assertGreater(float(evidence_row["eta_sq"]), 0.5)
        self.assertEqual(evidence_row["top_source"], "Source A")
        self.assertEqual(evidence_row["bottom_source"], "Source B")
        self.assertIn("p_perm_raw", evidence_row)
        self.assertIn("p_perm_fdr", evidence_row)
        self.assertIsInstance(evidence_row["p_perm_raw"], float)
        self.assertIsInstance(evidence_row["p_perm_fdr"], float)
        self.assertAlmostEqual(float(evidence_row["p_perm_raw"]), float(evidence_row["p_perm"]), places=9)
        self.assertGreaterEqual(float(evidence_row["p_perm_fdr"]), 0.0)
        self.assertLessEqual(float(evidence_row["p_perm_fdr"]), 1.0)
        self.assertIn("multiple_testing", effects)
        self.assertEqual(effects["multiple_testing"]["method"], "benjamini-hochberg")
        self.assertEqual(effects["multiple_testing"]["target"], "p_perm_raw")
        self.assertEqual(int(effects["multiple_testing"]["n_tests"]), 1)

        source_diff = stats["source_differentiation"]
        self.assertEqual(source_diff["status"], "ok")
        self.assertEqual(source_diff["n_articles"], 6)
        self.assertEqual(source_diff["n_sources"], 2)
        self.assertEqual(source_diff["n_lenses"], 1)
        self.assertEqual(source_diff["source_counts"].get("Source A"), 3)
        self.assertEqual(source_diff["source_counts"].get("Source B"), 3)
        self.assertIsInstance(source_diff["multivariate"], dict)
        self.assertIsInstance(source_diff["classification"], dict)
        self.assertGreater(float(source_diff["classification"]["accuracy"]), float(source_diff["classification"]["baseline_accuracy"]))

    def test_source_topic_control_duplicates_multi_topic_and_tracks_untagged(self):
        payload = {
            "analysis": {"lens_summary": {"lenses": [{"name": "Evidence", "max_total": 10.0}]}},
            "articles": [
                {
                    "id": "t-1",
                    "title": "Multi topic",
                    "published": "2026-03-02T03:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": ["Policy", "AI"],
                    "source": {"name": "Source A"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "Multi topic", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 60.0}}},
                },
                {
                    "id": "t-2",
                    "title": "Policy lower case",
                    "published": "2026-03-02T01:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": ["policy"],
                    "source": {"name": "Source B"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "Policy lower case", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 40.0}}},
                },
                {
                    "id": "t-3",
                    "title": "No topic tags",
                    "published": "2026-03-02T02:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": [],
                    "source": {"name": "Source C"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "No topic tags", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 50.0}}},
                },
            ],
        }

        records = normalize_articles(payload)
        stats = derive_stats(sort_records_desc(records), payload)
        topic_control = stats["source_topic_control"]
        topics = topic_control["topics"]

        self.assertEqual([row["topic"] for row in topics], ["Policy", "AI", "Untagged"])
        by_topic = {row["topic"]: row for row in topics}
        self.assertEqual(by_topic["Policy"]["n_articles"], 2)
        self.assertEqual(by_topic["Policy"]["n_sources"], 2)
        self.assertEqual(by_topic["AI"]["n_articles"], 1)
        self.assertEqual(by_topic["Untagged"]["n_articles"], 1)
        self.assertEqual(sum(row["n_articles"] for row in topics), 4)
        self.assertEqual(topic_control["summary"]["topic_count"], 3)
        source_reliability = stats["source_reliability"]
        self.assertEqual(source_reliability["summary"]["topic_count"], 3)
        self.assertEqual(len(source_reliability["topics"]), 3)

    def test_source_topic_control_marks_unavailable_topic_when_preconditions_fail(self):
        payload = {
            "analysis": {"lens_summary": {"lenses": [{"name": "Evidence", "max_total": 10.0}]}},
            "articles": [
                {
                    "id": "u-1",
                    "title": "Single source one",
                    "published": "2026-03-02T00:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": ["SingleTopic"],
                    "source": {"name": "Only Source"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "Single source one", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 60.0}}},
                },
                {
                    "id": "u-2",
                    "title": "Single source two",
                    "published": "2026-03-02T01:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": ["SingleTopic"],
                    "source": {"name": "Only Source"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "Single source two", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 55.0}}},
                },
            ],
        }

        records = normalize_articles(payload)
        stats = derive_stats(sort_records_desc(records), payload)
        topic_control = stats["source_topic_control"]
        self.assertEqual(topic_control["summary"]["topic_count"], 1)
        self.assertEqual(topic_control["summary"]["analyzed_topic_count"], 0)
        self.assertEqual(topic_control["summary"]["unavailable_topic_count"], 1)

        topic_row = topic_control["topics"][0]
        self.assertEqual(topic_row["topic"], "SingleTopic")
        self.assertEqual(topic_row["source_differentiation"]["status"], "unavailable")
        self.assertTrue(topic_row["source_differentiation"]["reason"])
        self.assertEqual(topic_row["source_lens_effects"]["status"], "unavailable")
        self.assertTrue(topic_row["source_lens_effects"]["reason"])

    def test_source_topic_control_can_reduce_pooled_confound_signal(self):
        articles = []
        for index, (source_suffix, score) in enumerate((("A", 92), ("A", 90), ("A", 88), ("B", 89)), start=1):
            articles.append(
                {
                    "id": f"topic1-{index}",
                    "title": f"Topic1 {index}",
                    "published": f"2026-03-02T0{index}:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": ["Topic1"],
                    "source": {"name": f"Source {source_suffix}"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": f"Topic1 {index}", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": float(score)}}},
                }
            )
        for index, (source_suffix, score) in enumerate((("A", 11), ("B", 9), ("B", 10), ("B", 12)), start=1):
            articles.append(
                {
                    "id": f"topic2-{index}",
                    "title": f"Topic2 {index}",
                    "published": f"2026-03-03T0{index}:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": ["Topic2"],
                    "source": {"name": f"Source {source_suffix}"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": f"Topic2 {index}", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": float(score)}}},
                }
            )

        payload = {
            "analysis": {"lens_summary": {"lenses": [{"name": "Evidence", "max_total": 10.0}]}},
            "articles": articles,
        }
        records = normalize_articles(payload)
        stats = derive_stats(sort_records_desc(records), payload)
        topic_control = stats["source_topic_control"]

        pooled_row = topic_control["pooled"]["source_lens_effects"]["rows"][0]
        pooled_eta = float(pooled_row["eta_sq"])
        topic_etas = []
        for topic_row in topic_control["topics"]:
            topic_rows = topic_row["source_lens_effects"]["rows"]
            self.assertTrue(topic_rows)
            topic_etas.append(float(topic_rows[0]["eta_sq"]))

        self.assertGreater(pooled_eta, max(topic_etas))
        self.assertEqual(topic_control["summary"]["topic_count"], 2)
        self.assertEqual(topic_control["summary"]["analyzed_topic_count"], 2)
        self.assertEqual(
            topic_control["pooled"]["source_lens_effects"]["multiple_testing"]["method"],
            "benjamini-hochberg",
        )
        for topic_row in topic_control["topics"]:
            topic_effects = topic_row["source_lens_effects"]
            self.assertEqual(topic_effects["multiple_testing"]["method"], "benjamini-hochberg")
            for effect_row in topic_effects["rows"]:
                self.assertIn("p_perm_raw", effect_row)
                self.assertIn("p_perm_fdr", effect_row)
                self.assertAlmostEqual(float(effect_row["p_perm_raw"]), float(effect_row["p_perm"]), places=9)
                self.assertGreaterEqual(float(effect_row["p_perm_fdr"]), 0.0)
                self.assertLessEqual(float(effect_row["p_perm_fdr"]), 1.0)

    def test_tag_sliced_analysis_duplicates_multi_tag_and_tracks_untagged(self):
        payload = {
            "analysis": {"lens_summary": {"lenses": [{"name": "Evidence", "max_total": 10.0}]}},
            "articles": [
                {
                    "id": "tag-1",
                    "title": "Multi tag",
                    "published": "2026-03-02T03:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": ["Policy", "AI"],
                    "source": {"name": "Source A"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "Multi tag", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 60.0}}},
                },
                {
                    "id": "tag-2",
                    "title": "Policy lower case",
                    "published": "2026-03-02T01:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": ["policy"],
                    "source": {"name": "Source B"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "Policy lower case", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 40.0}}},
                },
                {
                    "id": "tag-3",
                    "title": "No topic tags",
                    "published": "2026-03-02T02:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": [],
                    "source": {"name": "Source C"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "No topic tags", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 50.0}}},
                },
            ],
        }

        records = normalize_articles(payload)
        stats = derive_stats(sort_records_desc(records), payload)
        tag_sliced = stats["tag_sliced_analysis"]
        tag_rows = tag_sliced["tags"]

        self.assertEqual(tag_sliced["tag_basis"], "topic_tags")
        self.assertEqual(tag_sliced["multi_tag_policy"], "duplicate_per_tag")
        self.assertEqual([row["tag"] for row in tag_rows], ["Policy", "AI", "Untagged"])
        by_tag = {row["tag"]: row for row in tag_rows}
        self.assertEqual(by_tag["Policy"]["n_articles"], 2)
        self.assertEqual(by_tag["Policy"]["n_sources"], 2)
        self.assertEqual(by_tag["AI"]["n_articles"], 1)
        self.assertEqual(by_tag["Untagged"]["n_articles"], 1)
        self.assertEqual(by_tag["Policy"]["lens_summary"]["lenses"][0]["lens"], "Evidence")
        self.assertIn("daily_counts", by_tag["Policy"]["trends"])
        self.assertEqual(sum(row["n_articles"] for row in tag_rows), 4)
        self.assertEqual(tag_sliced["summary"]["tag_count"], 3)
        self.assertEqual(tag_sliced["summary"]["shown_tag_count"], 3)
        self.assertEqual(tag_sliced["summary"]["total_memberships"], 4)

    def test_tag_sliced_analysis_marks_unavailable_tag_when_preconditions_fail(self):
        payload = {
            "analysis": {"lens_summary": {"lenses": [{"name": "Evidence", "max_total": 10.0}]}},
            "articles": [
                {
                    "id": "tag-u-1",
                    "title": "Single source one",
                    "published": "2026-03-02T00:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": ["SingleTag"],
                    "source": {"name": "Only Source"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "Single source one", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 60.0}}},
                },
                {
                    "id": "tag-u-2",
                    "title": "Single source two",
                    "published": "2026-03-02T01:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": ["SingleTag"],
                    "source": {"name": "Only Source"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": "Single source two", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": 55.0}}},
                },
            ],
        }

        records = normalize_articles(payload)
        stats = derive_stats(sort_records_desc(records), payload)
        tag_sliced = stats["tag_sliced_analysis"]
        self.assertEqual(tag_sliced["summary"]["tag_count"], 1)
        self.assertEqual(tag_sliced["summary"]["analyzed_tag_count"], 0)
        self.assertEqual(tag_sliced["summary"]["unavailable_tag_count"], 1)

        tag_row = tag_sliced["tags"][0]
        self.assertEqual(tag_row["tag"], "SingleTag")
        self.assertEqual(tag_row["source_differentiation"]["status"], "unavailable")
        self.assertTrue(tag_row["source_differentiation"]["reason"])
        self.assertEqual(tag_row["source_lens_effects"]["status"], "unavailable")
        self.assertTrue(tag_row["source_lens_effects"]["reason"])

    def test_tag_sliced_analysis_can_reduce_pooled_confound_signal(self):
        articles = []
        for index, (source_suffix, score) in enumerate((("A", 92), ("A", 90), ("A", 88), ("B", 89)), start=1):
            articles.append(
                {
                    "id": f"tag1-{index}",
                    "title": f"Tag1 {index}",
                    "published": f"2026-03-02T0{index}:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": ["Tag1"],
                    "source": {"name": f"Source {source_suffix}"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": f"Tag1 {index}", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": float(score)}}},
                }
            )
        for index, (source_suffix, score) in enumerate((("A", 11), ("B", 9), ("B", 10), ("B", 12)), start=1):
            articles.append(
                {
                    "id": f"tag2-{index}",
                    "title": f"Tag2 {index}",
                    "published": f"2026-03-03T0{index}:00:00Z",
                    "ai_tags": ["X"],
                    "topic_tags": ["Tag2"],
                    "source": {"name": f"Source {source_suffix}"},
                    "feed": {"name": "Feed", "url": "https://example.com/feed"},
                    "scraped": {"title": f"Tag2 {index}", "body_text": "Body"},
                    "scrape_error": None,
                    "score": {"lens_scores": {"Evidence": {"percent": float(score)}}},
                }
            )

        payload = {
            "analysis": {"lens_summary": {"lenses": [{"name": "Evidence", "max_total": 10.0}]}},
            "articles": articles,
        }
        records = normalize_articles(payload)
        stats = derive_stats(sort_records_desc(records), payload)
        tag_sliced = stats["tag_sliced_analysis"]

        pooled_row = tag_sliced["pooled"]["source_lens_effects"]["rows"][0]
        pooled_eta = float(pooled_row["eta_sq"])
        tag_etas = []
        for tag_row in tag_sliced["tags"]:
            tag_rows = tag_row["source_lens_effects"]["rows"]
            self.assertTrue(tag_rows)
            tag_etas.append(float(tag_rows[0]["eta_sq"]))

        self.assertGreater(pooled_eta, max(tag_etas))
        self.assertEqual(tag_sliced["summary"]["tag_count"], 2)
        self.assertEqual(tag_sliced["summary"]["analyzed_tag_count"], 2)

    def test_source_lens_effects_fdr_is_monotonic_and_bounded(self):
        articles = []
        lens_specs = (
            ("Evidence", 88.0, 35.0),
            ("Balance", 62.0, 52.0),
            ("Tone", 50.0, 49.0),
        )
        topic_offsets = {"TopicA": 0.0, "TopicB": -8.0}
        article_idx = 0
        for topic_name in ("TopicA", "TopicB"):
            for source_name, source_shift in (("Source A", 0.0), ("Source B", 0.0)):
                for replicate in range(4):
                    article_idx += 1
                    lens_scores = {}
                    for lens_name, source_a_mean, source_b_mean in lens_specs:
                        baseline = source_a_mean if source_name == "Source A" else source_b_mean
                        jitter = float((replicate % 2) * 1.5)
                        lens_scores[lens_name] = {
                            "percent": baseline + topic_offsets[topic_name] + jitter
                        }
                    articles.append(
                        {
                            "id": f"fdr-{article_idx}",
                            "title": f"{topic_name} {source_name} {replicate}",
                            "published": f"2026-03-{2 + (article_idx // 12):02d}T0{(article_idx % 9)}:00:00Z",
                            "ai_tags": ["X"],
                            "topic_tags": [topic_name],
                            "source": {"name": source_name},
                            "feed": {"name": "Feed", "url": "https://example.com/feed"},
                            "scraped": {"title": f"{topic_name} {source_name}", "body_text": "Body"},
                            "scrape_error": None,
                            "score": {"lens_scores": lens_scores},
                        }
                    )

        payload = {
            "analysis": {
                "lens_summary": {
                    "lenses": [
                        {"name": "Evidence", "max_total": 10.0},
                        {"name": "Balance", "max_total": 10.0},
                        {"name": "Tone", "max_total": 10.0},
                    ]
                }
            },
            "articles": articles,
        }
        records = normalize_articles(payload)
        stats = derive_stats(sort_records_desc(records), payload)

        pooled_effects = stats["source_lens_effects"]
        self.assertEqual(pooled_effects["status"], "ok")
        self.assertEqual(pooled_effects["multiple_testing"]["method"], "benjamini-hochberg")
        pooled_rows = pooled_effects["rows"]
        self.assertGreaterEqual(len(pooled_rows), 3)
        self.assertEqual(
            pooled_effects["multiple_testing"]["n_tests"],
            sum(1 for row in pooled_rows if isinstance(row.get("p_perm_raw"), float)),
        )

        previous_q = 0.0
        for row in pooled_rows:
            p_raw = row.get("p_perm_raw")
            p_fdr = row.get("p_perm_fdr")
            self.assertIsInstance(p_raw, float)
            self.assertIsInstance(p_fdr, float)
            self.assertGreaterEqual(p_raw, 0.0)
            self.assertLessEqual(p_raw, 1.0)
            self.assertGreaterEqual(p_fdr, 0.0)
            self.assertLessEqual(p_fdr, 1.0)
            self.assertGreaterEqual(p_fdr + 1e-12, p_raw)
            self.assertGreaterEqual(p_fdr + 1e-12, previous_q)
            previous_q = p_fdr

        topic_control = stats["source_topic_control"]
        for topic_row in topic_control["topics"]:
            topic_effects = topic_row["source_lens_effects"]
            self.assertEqual(topic_effects["multiple_testing"]["method"], "benjamini-hochberg")
            self.assertGreaterEqual(topic_effects["multiple_testing"]["n_tests"], 0)

    def test_last_good_fallback(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp:
            json.dump(SAMPLE_PAYLOAD, temp)
            temp_path = Path(temp.name)

        client = RssDigestClient(source_url=f"file://{temp_path}", ttl_seconds=1, timeout_seconds=2)
        first = client.get_payload(force_refresh=True)
        self.assertFalse(first["using_last_good"])
        self.assertEqual(len(first["articles_normalized"]), 2)

        client.current_source_url = "https://127.0.0.1:1/not-available.json"
        second = client.get_payload(force_refresh=True)
        self.assertTrue(second["using_last_good"])
        self.assertTrue(second["error"])

        temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
