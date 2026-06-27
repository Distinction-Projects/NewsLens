import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.services.news_stats_snapshot import PrecomputedStatsError, load_precomputed_stats_response


def _snapshot(total_articles: int, *, marker: str = "", generated_at: str | None = None) -> dict:
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "status": "ok",
        "meta": {"source_url": "file://snapshot.json", "marker": marker, "generated_at": generated_at},
        "data": {
            "derived": {"total_articles": total_articles},
            "summary": {},
            "analysis": {},
        },
    }


class NewsStatsSnapshotTests(unittest.TestCase):
    def test_precomputed_snapshot_cache_is_copy_safe_and_reloads_on_file_change(self):
        with tempfile.TemporaryDirectory(prefix="news-stats-snapshot-") as temp_dir:
            path = Path(temp_dir) / "stats.json"
            path.write_text(json.dumps(_snapshot(1)), encoding="utf-8")

            first = load_precomputed_stats_response(path)
            first["data"]["derived"]["total_articles"] = 999

            second = load_precomputed_stats_response(path)
            self.assertEqual(second["data"]["derived"]["total_articles"], 1)
            self.assertEqual(second["meta"]["stats_backend"], "precomputed")

            path.write_text(json.dumps(_snapshot(2, marker="changed-and-longer")), encoding="utf-8")

            third = load_precomputed_stats_response(path)
            self.assertEqual(third["data"]["derived"]["total_articles"], 2)
            self.assertEqual(third["meta"]["marker"], "changed-and-longer")

    def test_precomputed_snapshot_rejects_stale_content_timestamp(self):
        with tempfile.TemporaryDirectory(prefix="news-stats-snapshot-") as temp_dir:
            stale_timestamp = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat().replace("+00:00", "Z")
            path = Path(temp_dir) / "stats.json"
            path.write_text(json.dumps(_snapshot(1, generated_at=stale_timestamp)), encoding="utf-8")

            with self.assertRaisesRegex(PrecomputedStatsError, "snapshot is stale"):
                load_precomputed_stats_response(path, max_age_seconds=36 * 3600)

    def test_precomputed_snapshot_accepts_fresh_content_timestamp(self):
        with tempfile.TemporaryDirectory(prefix="news-stats-snapshot-") as temp_dir:
            path = Path(temp_dir) / "stats.json"
            path.write_text(json.dumps(_snapshot(1)), encoding="utf-8")

            payload = load_precomputed_stats_response(path, max_age_seconds=36 * 3600)

            self.assertEqual(payload["data"]["derived"]["total_articles"], 1)


if __name__ == "__main__":
    unittest.main()
