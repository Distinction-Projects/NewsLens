import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask

from src.api.news_endpoints import register_news_endpoints


NOW_UTC = datetime.now(timezone.utc)
NOW_UTC_ISO = NOW_UTC.isoformat().replace("+00:00", "Z")
DIGEST_UTC_ISO = (NOW_UTC - timedelta(minutes=3)).isoformat().replace("+00:00", "Z")


SAMPLE_PAYLOAD = {
    "schema_version": "1.0",
    "generated_at": NOW_UTC_ISO,
    "contract": "rss_pipeline_precomputed",
    "digest": {
        "generated_at": DIGEST_UTC_ISO,
        "run_id": "digest-abc123",
    },
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
            "published": "2026-03-03T03:10:00Z",
            "summary": "Summary 3",
            "ai_summary": "AI Summary 3",
            "ai_tags": ["OpenAI"],
            "topic_tags": ["General"],
            "source": {"id": "failed-source", "name": "Failed Source"},
            "feed": {"name": "Errors", "url": "https://example.com/errors"},
            "scraped": None,
            "scrape_error": "HTTP 500",
            "score": {"value": 20.0, "max_value": 20.0, "percent": 100.0, "rubric_count": 3},
        },
    ],
}


class NewsEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="rss-news-endpoints-"))
        cls.current_payload_path = cls.temp_dir / "rss_openai_precomputed.json"
        cls.current_payload_path.write_text(json.dumps(SAMPLE_PAYLOAD), encoding="utf-8")

        cls.snapshot_date = "2026-03-10"
        cls.snapshot_payload_path = cls.temp_dir / f"rss_openai_daily_{cls.snapshot_date}.json"
        cls.snapshot_payload_path.write_text(json.dumps(SAMPLE_PAYLOAD), encoding="utf-8")

        os.environ["RSS_DAILY_JSON_URL"] = f"file://{cls.current_payload_path}"
        os.environ["RSS_HISTORY_JSON_URL_TEMPLATE"] = f"file://{cls.temp_dir}/rss_openai_daily_{{date}}.json"
        os.environ["RSS_CACHE_TTL_SECONDS"] = "60"
        os.environ["RSS_HTTP_TIMEOUT_SECONDS"] = "5"
        os.environ["RSS_MAX_AGE_SECONDS"] = "172800"

        app = Flask(__name__)
        register_news_endpoints(app)
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_digest_and_filters(self):
        response = self.client.get("/api/news/digest")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(len(payload["data"]), 2)
        self.assertEqual(payload["meta"]["input_articles_count"], 3)
        self.assertEqual(payload["meta"]["excluded_unscraped_articles"], 1)

        response = self.client.get("/api/news/digest?tag=openai")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["data"]), 2)

        response = self.client.get("/api/news/digest?source=pbs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["data"]), 1)

    def test_latest_and_bad_limit(self):
        latest = self.client.get("/api/news/digest/latest")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.get_json()["data"]["id"], "a-1")
        self.assertEqual(latest.get_json()["meta"]["excluded_unscraped_articles"], 1)

        bad_limit = self.client.get("/api/news/digest?limit=0")
        self.assertEqual(bad_limit.status_code, 400)

    def test_snapshot_date_routing_and_meta(self):
        response = self.client.get(f"/api/news/digest?snapshot_date={self.snapshot_date}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["filters"]["snapshot_date"], self.snapshot_date)
        self.assertEqual(payload["meta"]["source_mode"], "snapshot")
        self.assertEqual(payload["meta"]["snapshot_date"], self.snapshot_date)
        self.assertIn(f"rss_openai_daily_{self.snapshot_date}.json", payload["meta"]["source_url"])

        latest = self.client.get(f"/api/news/digest/latest?snapshot_date={self.snapshot_date}")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.get_json()["meta"]["source_mode"], "snapshot")

        stats = self.client.get(f"/api/news/stats?snapshot_date={self.snapshot_date}")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.get_json()["meta"]["source_mode"], "snapshot")

    def test_snapshot_date_validation_and_missing_file(self):
        bad_date = self.client.get("/api/news/digest?snapshot_date=2026/03/10")
        self.assertEqual(bad_date.status_code, 400)
        self.assertEqual(bad_date.get_json()["status"], "bad_request")

        missing_snapshot = self.client.get("/api/news/digest?snapshot_date=2026-03-09")
        self.assertEqual(missing_snapshot.status_code, 404)
        self.assertEqual(missing_snapshot.get_json()["status"], "not_found")

        missing_stats = self.client.get("/api/news/stats?snapshot_date=2026-03-09")
        self.assertEqual(missing_stats.status_code, 404)
        self.assertEqual(missing_stats.get_json()["status"], "not_found")

    def test_stats_and_freshness(self):
        stats = self.client.get("/api/news/stats")
        self.assertEqual(stats.status_code, 200)
        self.assertIn("public, max-age=", stats.headers.get("Cache-Control", ""))
        stats_payload = stats.get_json()
        self.assertEqual(stats_payload["status"], "ok")
        self.assertIn("derived", stats_payload["data"])
        self.assertEqual(stats_payload["data"]["derived"]["input_articles"], 3)
        self.assertEqual(stats_payload["data"]["derived"]["excluded_unscraped_articles"], 1)
        self.assertEqual(stats_payload["data"]["derived"]["total_articles"], 2)
        self.assertEqual(stats_payload["data"]["derived"]["scored_articles"], 1)
        self.assertEqual(stats_payload["data"]["derived"]["zero_score_articles"], 0)
        self.assertEqual(stats_payload["data"]["derived"]["unscorable_articles"], 1)
        self.assertIn("score_status", stats_payload["data"]["derived"])
        self.assertEqual(stats_payload["data"]["derived"]["score_status"]["scored"], 1)
        self.assertEqual(stats_payload["data"]["derived"]["score_status"]["unscorable"], 1)
        self.assertIn("lens_correlations", stats_payload["data"]["derived"])
        self.assertIn("source_differentiation", stats_payload["data"]["derived"])
        self.assertIn("source_lens_effects", stats_payload["data"]["derived"])
        self.assertIn("lens_views", stats_payload["data"]["derived"])
        self.assertIn("lens_inventory", stats_payload["data"]["derived"])
        self.assertIn("lens_pca", stats_payload["data"]["derived"])
        self.assertIn("lens_mds", stats_payload["data"]["derived"])
        self.assertIn("lens_separation", stats_payload["data"]["derived"])
        self.assertIn("lens_time_series", stats_payload["data"]["derived"])
        self.assertIn("lens_temporal_embedding", stats_payload["data"]["derived"])
        self.assertIn("lens_temporal_embedding_mds", stats_payload["data"]["derived"])
        lens_correlations = stats_payload["data"]["derived"]["lens_correlations"]
        self.assertIn("lenses", lens_correlations)
        self.assertIn("correlation", lens_correlations)
        self.assertIn("covariance", lens_correlations)
        self.assertIn("pairwise_counts", lens_correlations)
        self.assertIn("pair_rankings", lens_correlations)
        self.assertIn("summary_by_matrix", lens_correlations)
        self.assertEqual(sorted(lens_correlations["pair_rankings"].keys()), ["corr_norm", "corr_raw", "cov_norm", "cov_raw", "pairwise"])
        self.assertEqual(sorted(lens_correlations["summary_by_matrix"].keys()), ["corr_norm", "corr_raw", "cov_norm", "cov_raw", "pairwise"])
        self.assertEqual(lens_correlations["summary_by_matrix"]["corr_raw"]["pair_count"], 0)
        self.assertIsNone(lens_correlations["summary_by_matrix"]["corr_raw"]["strongest_pair"])
        source_differentiation = stats_payload["data"]["derived"]["source_differentiation"]
        self.assertIn("status", source_differentiation)
        self.assertIn("source_counts", source_differentiation)
        self.assertIn("multivariate", source_differentiation)
        self.assertIn("classification", source_differentiation)
        source_lens_effects = stats_payload["data"]["derived"]["source_lens_effects"]
        self.assertIn("status", source_lens_effects)
        self.assertIn("permutations", source_lens_effects)
        self.assertIn("rows", source_lens_effects)
        source_topic_control = stats_payload["data"]["derived"]["source_topic_control"]
        self.assertEqual(source_topic_control["topic_basis"], "topic_tags")
        self.assertEqual(source_topic_control["multi_topic_policy"], "duplicate_per_topic")
        self.assertEqual(source_topic_control["pooled_label"], "topic-confounded")
        self.assertIn("topics", source_topic_control)
        self.assertIn("summary", source_topic_control)
        self.assertEqual(
            source_topic_control["pooled"]["source_differentiation"],
            source_differentiation,
        )
        self.assertEqual(
            source_topic_control["pooled"]["source_lens_effects"],
            source_lens_effects,
        )
        tag_sliced_analysis = stats_payload["data"]["derived"]["tag_sliced_analysis"]
        self.assertEqual(tag_sliced_analysis["tag_basis"], "topic_tags")
        self.assertEqual(tag_sliced_analysis["multi_tag_policy"], "duplicate_per_tag")
        self.assertEqual(tag_sliced_analysis["pooled_label"], "tag-confounded")
        self.assertIn("tags", tag_sliced_analysis)
        self.assertIn("summary", tag_sliced_analysis)
        self.assertEqual(
            tag_sliced_analysis["pooled"]["source_differentiation"],
            source_differentiation,
        )
        self.assertEqual(
            tag_sliced_analysis["pooled"]["source_lens_effects"],
            source_lens_effects,
        )
        event_control = stats_payload["data"]["derived"]["event_control"]
        self.assertIn(event_control["status"], {"ok", "unavailable"})
        self.assertIn("config", event_control)
        self.assertIn("summary", event_control)
        self.assertIn("events", event_control)
        self.assertIn("same_event_source_differentiation", event_control)
        self.assertIn("same_event_source_lens_effects", event_control)
        self.assertIn("same_event_pairwise_source_lens_deltas", event_control)
        self.assertIn("event_coverage", event_control)
        self.assertIn("same_event_variance_decomposition", event_control)
        self.assertIn("source_reliability", stats_payload["data"]["derived"])
        source_reliability = stats_payload["data"]["derived"]["source_reliability"]
        self.assertEqual(source_reliability["method"], "heuristic-v1")
        self.assertEqual(source_reliability["pooled_label"], "topic-confounded")
        self.assertIn("pooled", source_reliability)
        self.assertIn("topics", source_reliability)
        self.assertIn("tags", source_reliability)
        self.assertIn("summary", source_reliability)
        self.assertIn("tag_count", source_reliability["summary"])
        self.assertIn("ok_tag_count", source_reliability["summary"])
        self.assertIn(source_reliability["pooled"].get("status"), {"ok", "unavailable"})
        lens_pca = stats_payload["data"]["derived"]["lens_pca"]
        self.assertIn("status", lens_pca)
        self.assertIn("reason", lens_pca)
        self.assertIn("components", lens_pca)
        self.assertIn("explained_variance", lens_pca)
        self.assertIn("variance_drivers", lens_pca)
        self.assertIn("article_points", lens_pca)
        self.assertIn("source_centroids", lens_pca)
        lens_mds = stats_payload["data"]["derived"]["lens_mds"]
        self.assertIn("status", lens_mds)
        self.assertIn("reason", lens_mds)
        self.assertIn("dimensions", lens_mds)
        self.assertIn("dimension_strength", lens_mds)
        self.assertIn("stress", lens_mds)
        self.assertIn("article_points", lens_mds)
        self.assertIn("source_centroids", lens_mds)
        lens_separation = stats_payload["data"]["derived"]["lens_separation"]
        self.assertIn("status", lens_separation)
        self.assertIn("reason", lens_separation)
        self.assertIn("n_sources", lens_separation)
        self.assertIn("separation_ratio", lens_separation)
        self.assertIn("silhouette_like_mean", lens_separation)
        lens_time_series = stats_payload["data"]["derived"]["lens_time_series"]
        self.assertIn("status", lens_time_series)
        self.assertIn("reason", lens_time_series)
        self.assertIn("series", lens_time_series)
        self.assertIn("summary", lens_time_series)
        lens_temporal_embedding = stats_payload["data"]["derived"]["lens_temporal_embedding"]
        self.assertIn("status", lens_temporal_embedding)
        self.assertIn("reason", lens_temporal_embedding)
        self.assertIn("points", lens_temporal_embedding)
        self.assertIn("summary", lens_temporal_embedding)
        lens_temporal_embedding_mds = stats_payload["data"]["derived"]["lens_temporal_embedding_mds"]
        self.assertIn("status", lens_temporal_embedding_mds)
        self.assertIn("reason", lens_temporal_embedding_mds)
        self.assertIn("points", lens_temporal_embedding_mds)
        self.assertIn("summary", lens_temporal_embedding_mds)
        lens_views = stats_payload["data"]["derived"]["lens_views"]
        self.assertIn("coverage_mode", lens_views)
        self.assertIn("lens_names", lens_views)
        self.assertIn("article_rows", lens_views)
        self.assertIn("source_rows", lens_views)
        self.assertIn("stability_rows", lens_views)
        self.assertIn("summary", lens_views)
        self.assertEqual(lens_views["summary"]["article_count"], 1)
        self.assertIsInstance(lens_views["summary"]["dominant_lens_counts"], list)
        self.assertIsInstance(lens_views["summary"]["lens_average_rows"], list)
        self.assertEqual(lens_views["summary"]["source_count"], 1)
        self.assertEqual(lens_views["summary"]["covered_articles"], 1)
        self.assertIsInstance(lens_views["summary"]["source_lens_average_rows"], list)
        self.assertEqual(lens_views["summary"]["stability_lens_count"], 1)
        self.assertEqual(lens_views["summary"]["stability_avg_stddev"], 0.0)
        self.assertEqual(lens_views["summary"]["stability_top_lens"], "L1")
        self.assertEqual(lens_views["summary"]["stability_total_samples"], 1)
        lens_inventory = stats_payload["data"]["derived"]["lens_inventory"]
        self.assertIn("coverage_mode", lens_inventory)
        self.assertIn("items_total", lens_inventory)
        self.assertIn("aggregation", lens_inventory)
        self.assertIn("lenses", lens_inventory)
        self.assertIn("data_quality", stats_payload["data"]["derived"])
        data_quality = stats_payload["data"]["derived"]["data_quality"]
        self.assertIn("summary", data_quality)
        self.assertIn("field_coverage", data_quality)
        self.assertEqual(data_quality["summary"]["total"], 2)
        self.assertEqual(data_quality["summary"]["scored"], 1)
        self.assertEqual(data_quality["summary"]["missing_ai_summary"], 0)
        self.assertEqual(data_quality["summary"]["missing_published"], 0)
        self.assertEqual(data_quality["summary"]["missing_source"], 0)
        coverage_by_field = {row["field"]: row for row in data_quality["field_coverage"]}
        self.assertEqual(coverage_by_field["Title"]["present"], 2)
        self.assertEqual(coverage_by_field["Lens Scores"]["present"], 1)
        chart_aggregates = stats_payload["data"]["derived"]["chart_aggregates"]
        self.assertEqual(len(chart_aggregates["tag_count_distribution"]), 6)
        self.assertEqual(len(chart_aggregates["publish_hour_counts_utc"]), 24)
        self.assertIn("source_tag_totals", chart_aggregates)
        self.assertIn("tag_totals", chart_aggregates)
        self.assertIn("score_status_by_source", chart_aggregates)
        self.assertEqual(chart_aggregates["source_tag_totals"][0]["source"], "PBS NewsHour")
        self.assertEqual(chart_aggregates["source_tag_totals"][0]["count"], 3)
        self.assertEqual(chart_aggregates["tag_totals"][0]["tag"], "OpenAI")
        self.assertEqual(chart_aggregates["tag_totals"][0]["count"], 2)
        source_tag_views = stats_payload["data"]["derived"]["source_tag_views"]
        self.assertIn("source_labels", source_tag_views)
        self.assertIn("tag_labels", source_tag_views)
        self.assertIn("source_rows", source_tag_views)
        self.assertIn("summary", source_tag_views)
        self.assertEqual(source_tag_views["source_labels"][0], "PBS NewsHour")
        self.assertEqual(source_tag_views["tag_labels"][0], "OpenAI")
        self.assertEqual(source_tag_views["source_rows"][0]["source"], "PBS NewsHour")
        self.assertEqual(source_tag_views["summary"]["source_count"], 2)
        self.assertEqual(source_tag_views["summary"]["tag_count"], 4)
        self.assertEqual(source_tag_views["summary"]["matrix_rows"], 5)
        self.assertEqual(source_tag_views["summary"]["non_zero_cells"], 5)
        self.assertEqual(source_tag_views["summary"]["total_assignments"], 5)

        health = self.client.get("/health/news-freshness")
        self.assertEqual(health.status_code, 200)
        health_payload = health.get_json()
        self.assertTrue(health_payload["is_fresh"])

    def test_upstream_endpoint(self):
        response = self.client.get("/api/news/upstream")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("meta", payload)
        self.assertIn("data", payload)
        upstream = payload["data"]["upstream"]
        self.assertIsInstance(upstream, dict)
        self.assertIn("articles", upstream)
        self.assertEqual(len(upstream["articles"]), 3)
        self.assertEqual(upstream["articles"][0]["id"], "a-1")

        snapshot_response = self.client.get(f"/api/news/upstream?snapshot_date={self.snapshot_date}")
        self.assertEqual(snapshot_response.status_code, 200)
        snapshot_payload = snapshot_response.get_json()
        self.assertEqual(snapshot_payload["meta"]["source_mode"], "snapshot")
        self.assertEqual(snapshot_payload["meta"]["snapshot_date"], self.snapshot_date)

    def test_export_endpoints(self):
        export_json = self.client.get("/api/news/export?artifact=source_score_status&format=json")
        self.assertEqual(export_json.status_code, 200)
        payload = export_json.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["artifact"], "source_score_status")
        self.assertIsInstance(payload["rows"], list)
        self.assertGreaterEqual(len(payload["rows"]), 1)

        export_csv = self.client.get("/api/news/export?artifact=source_score_status&format=csv")
        self.assertEqual(export_csv.status_code, 200)
        self.assertIn("text/csv", export_csv.content_type)
        csv_body = export_csv.get_data(as_text=True)
        self.assertIn("source", csv_body)
        self.assertIn("scored", csv_body)

        export_source_effects = self.client.get("/api/news/export?artifact=source_lens_effects&format=json")
        self.assertEqual(export_source_effects.status_code, 200)
        effects_payload = export_source_effects.get_json()
        self.assertEqual(effects_payload["artifact"], "source_lens_effects")
        self.assertIsInstance(effects_payload["rows"], list)

        export_source_summary = self.client.get("/api/news/export?artifact=source_differentiation_summary&format=json")
        self.assertEqual(export_source_summary.status_code, 200)
        source_summary_payload = export_source_summary.get_json()
        self.assertEqual(source_summary_payload["artifact"], "source_differentiation_summary")
        self.assertIsInstance(source_summary_payload["rows"], list)
        self.assertEqual(len(source_summary_payload["rows"]), 1)

        export_event_summary = self.client.get("/api/news/export?artifact=event_control_summary&format=json")
        self.assertEqual(export_event_summary.status_code, 200)
        event_summary_payload = export_event_summary.get_json()
        self.assertEqual(event_summary_payload["artifact"], "event_control_summary")
        self.assertIsInstance(event_summary_payload["rows"], list)
        self.assertEqual(len(event_summary_payload["rows"]), 1)
        self.assertIn("event_count", event_summary_payload["rows"][0])

        export_events = self.client.get("/api/news/export?artifact=event_clusters&format=json")
        self.assertEqual(export_events.status_code, 200)
        events_payload = export_events.get_json()
        self.assertEqual(events_payload["artifact"], "event_clusters")
        self.assertIsInstance(events_payload["rows"], list)

        export_source_coverage = self.client.get("/api/news/export?artifact=event_source_coverage&format=json")
        self.assertEqual(export_source_coverage.status_code, 200)
        source_coverage_payload = export_source_coverage.get_json()
        self.assertEqual(source_coverage_payload["artifact"], "event_source_coverage")
        self.assertIsInstance(source_coverage_payload["rows"], list)

        export_pair_coverage = self.client.get("/api/news/export?artifact=event_source_pair_coverage&format=json")
        self.assertEqual(export_pair_coverage.status_code, 200)
        pair_coverage_payload = export_pair_coverage.get_json()
        self.assertEqual(pair_coverage_payload["artifact"], "event_source_pair_coverage")
        self.assertIsInstance(pair_coverage_payload["rows"], list)

        export_same_event_effects = self.client.get("/api/news/export?artifact=same_event_source_lens_effects&format=json")
        self.assertEqual(export_same_event_effects.status_code, 200)
        same_event_effects_payload = export_same_event_effects.get_json()
        self.assertEqual(same_event_effects_payload["artifact"], "same_event_source_lens_effects")
        self.assertIsInstance(same_event_effects_payload["rows"], list)

        export_pairwise_deltas = self.client.get("/api/news/export?artifact=same_event_pairwise_source_lens_deltas&format=json")
        self.assertEqual(export_pairwise_deltas.status_code, 200)
        pairwise_deltas_payload = export_pairwise_deltas.get_json()
        self.assertEqual(pairwise_deltas_payload["artifact"], "same_event_pairwise_source_lens_deltas")
        self.assertIsInstance(pairwise_deltas_payload["rows"], list)

        export_variance = self.client.get("/api/news/export?artifact=same_event_variance_decomposition&format=json")
        self.assertEqual(export_variance.status_code, 200)
        variance_payload = export_variance.get_json()
        self.assertEqual(variance_payload["artifact"], "same_event_variance_decomposition")
        self.assertIsInstance(variance_payload["rows"], list)

        export_same_event_summary = self.client.get(
            "/api/news/export?artifact=same_event_source_differentiation_summary&format=json"
        )
        self.assertEqual(export_same_event_summary.status_code, 200)
        same_event_summary_payload = export_same_event_summary.get_json()
        self.assertEqual(same_event_summary_payload["artifact"], "same_event_source_differentiation_summary")
        self.assertIsInstance(same_event_summary_payload["rows"], list)
        self.assertEqual(len(same_event_summary_payload["rows"]), 1)

        bad_artifact = self.client.get("/api/news/export?artifact=unknown")
        self.assertEqual(bad_artifact.status_code, 400)

        bad_format = self.client.get("/api/news/export?artifact=source_score_status&format=xml")
        self.assertEqual(bad_format.status_code, 400)

    def test_freshness_is_stale_when_generated_at_missing(self):
        payload = dict(SAMPLE_PAYLOAD)
        payload.pop("generated_at", None)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp:
            json.dump(payload, temp)
            temp.flush()
            temp_path = Path(temp.name)

        previous_url = os.environ.get("RSS_DAILY_JSON_URL")
        try:
            os.environ["RSS_DAILY_JSON_URL"] = f"file://{temp_path}"
            app = Flask(__name__)
            register_news_endpoints(app)
            client = app.test_client()

            response = client.get("/health/news-freshness?refresh=true")
            self.assertEqual(response.status_code, 503)
            body = response.get_json()
            self.assertEqual(body["status"], "stale")
            self.assertFalse(body["is_fresh"])
            self.assertEqual(body["reason"], "generated_at is missing from payload")
        finally:
            if previous_url is None:
                os.environ.pop("RSS_DAILY_JSON_URL", None)
            else:
                os.environ["RSS_DAILY_JSON_URL"] = previous_url
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
