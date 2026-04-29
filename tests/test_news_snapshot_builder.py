import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.analytics.build_news_snapshot import build_stats_snapshot


NOW_UTC_ISO = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class NewsSnapshotBuilderTests(unittest.TestCase):
    def test_build_stats_snapshot_writes_existing_stats_envelope(self):
        with tempfile.TemporaryDirectory(prefix="news-snapshot-builder-") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            source_path = temp_dir / "rss_openai_precomputed.json"
            output_path = temp_dir / "news_analytics_snapshot.json"
            source_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "generated_at": NOW_UTC_ISO,
                        "contract": "rss_pipeline_precomputed",
                        "digest": {"generated_at": NOW_UTC_ISO, "run_id": "digest-snapshot-builder"},
                        "summary": {"articles": 1, "scored_articles": 1},
                        "analysis": {"lens_summary": {"lenses": [{"name": "Evidence", "max_total": 10.0}]}},
                        "articles": [
                            {
                                "id": "snapshot-1",
                                "title": "Snapshot Story",
                                "link": "https://example.com/snapshot",
                                "published": NOW_UTC_ISO,
                                "summary": "Summary",
                                "ai_summary": "AI Summary",
                                "ai_tags": ["OpenAI"],
                                "topic_tags": ["Policy"],
                                "source": {"id": "source-a", "name": "Source A"},
                                "feed": {"name": "Feed", "url": "https://example.com/feed"},
                                "scraped": {"title": "Snapshot Story", "body_text": "Body"},
                                "scrape_error": None,
                                "score": {"lens_scores": {"Evidence": {"percent": 75.0}}},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = build_stats_snapshot(output_path=output_path, source_url=f"file://{source_path}")

            self.assertTrue(output_path.exists())
            written = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(written["status"], "ok")
            self.assertIn("meta", written)
            self.assertIn("data", written)
            self.assertIn("derived", written["data"])
            self.assertIn("tag_sliced_analysis", written["data"]["derived"])
            self.assertIn("event_control", written["data"]["derived"])
            self.assertEqual(written["meta"]["stats_backend"], "precomputed")
            self.assertEqual(written["snapshot"]["snapshot_schema_version"], "1.0")


if __name__ == "__main__":
    unittest.main()
