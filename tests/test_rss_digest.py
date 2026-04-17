import json
import tempfile
import unittest
from pathlib import Path

from src.services.rss_digest import (
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
        self.assertIn("rows", stats["source_lens_effects"])
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
