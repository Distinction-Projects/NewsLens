import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.api.news_controller import NewsController
from src.services.rss_digest import RssDigestClient


NOW_UTC_ISO = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


SAMPLE_PAYLOAD = {
    "schema_version": "1.0",
    "generated_at": NOW_UTC_ISO,
    "contract": "rss_pipeline_precomputed",
    "digest": {"generated_at": NOW_UTC_ISO, "run_id": "digest-controller"},
    "summary": {"articles": 1, "scored_articles": 1},
    "analysis": {},
    "articles": [
        {
            "id": "a-1",
            "title": "Controller Story",
            "link": "https://example.com/controller",
            "published": NOW_UTC_ISO,
            "summary": "Summary",
            "ai_summary": "AI Summary",
            "ai_tags": ["OpenAI"],
            "topic_tags": ["General"],
            "source": {"id": "source-a", "name": "Source A"},
            "feed": {"name": "Feed", "url": "https://example.com/feed"},
            "scraped": {"title": "Controller Story", "body_text": "Body"},
            "scrape_error": None,
            "score": {"value": 12.0, "max_value": 20.0, "percent": 60.0, "rubric_count": 2},
        }
    ],
}


class NewsControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="rss-news-controller-"))
        cls.current_payload_path = cls.temp_dir / "rss_openai_precomputed.json"
        cls.current_payload_path.write_text(json.dumps(SAMPLE_PAYLOAD), encoding="utf-8")

        os.environ["RSS_DAILY_JSON_URL"] = f"file://{cls.current_payload_path}"
        os.environ["RSS_CACHE_TTL_SECONDS"] = "60"
        os.environ["RSS_HTTP_TIMEOUT_SECONDS"] = "5"
        os.environ["RSS_MAX_AGE_SECONDS"] = "172800"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_digest_rejects_invalid_limit(self):
        controller = NewsController(RssDigestClient())
        response = controller.get_digest(
            refresh=None,
            date=None,
            tag=None,
            source=None,
            limit="0",
            snapshot_date=None,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content_type, "application/json")
        self.assertIsInstance(response.body, dict)
        self.assertEqual(response.body.get("status"), "bad_request")

    def test_digest_success_sets_cache_headers_and_refresh_disables_cache(self):
        controller = NewsController(RssDigestClient())
        cached = controller.get_digest(
            refresh=None,
            date=None,
            tag=None,
            source=None,
            limit="1",
            snapshot_date=None,
        )
        self.assertEqual(cached.status_code, 200)
        self.assertIn("public, max-age=", cached.headers.get("Cache-Control", ""))

        refreshed = controller.get_digest(
            refresh="1",
            date=None,
            tag=None,
            source=None,
            limit="1",
            snapshot_date=None,
        )
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual(refreshed.headers.get("Cache-Control"), "no-store")

    def test_export_csv_uses_csv_response_contract(self):
        controller = NewsController(RssDigestClient())
        response = controller.export_artifact(
            refresh=None,
            artifact="event_control_summary",
            export_format="csv",
            snapshot_date=None,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "text/csv; charset=utf-8")
        self.assertIn("Content-Disposition", response.headers)
        self.assertIsInstance(response.body, str)
        self.assertIn("event_control_summary.csv", response.headers["Content-Disposition"])
        self.assertIn("event_count", response.body)


if __name__ == "__main__":
    unittest.main()
