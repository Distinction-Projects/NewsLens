import json
import tempfile
import unittest
from pathlib import Path

from src.services.news_stats_snapshot import load_precomputed_stats_response


def _snapshot(total_articles: int, *, marker: str = "") -> dict:
    return {
        "status": "ok",
        "meta": {"source_url": "file://snapshot.json", "marker": marker},
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


if __name__ == "__main__":
    unittest.main()
