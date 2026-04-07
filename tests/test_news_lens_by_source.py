import unittest

import src.app  # noqa: F401
from src.pages.news_lens_by_source import _source_lens_rows


class NewsLensBySourceTests(unittest.TestCase):
    def test_source_lens_rows_prefer_full_score_data(self):
        rows, lens_names, coverage = _source_lens_rows(
            [
                {
                    "source": {"name": "Source A"},
                    "score": {"percent": 60.0, "lens_scores": {"Evidence": {"percent": 70.0}, "Impact": {"percent": 50.0}}},
                    "high_score": {"overall_percent": 60.0, "lens_scores": {"Evidence": 7.0}},
                },
                {
                    "source": {"name": "Source A"},
                    "score": {"percent": 80.0, "lens_scores": {"Evidence": {"percent": 90.0}, "Impact": {"percent": 60.0}}},
                    "high_score": {"overall_percent": 80.0, "lens_scores": {"Evidence": 9.0}},
                },
            ],
            {"Evidence": 10.0, "Impact": 10.0},
        )

        self.assertEqual(coverage, "all scored articles")
        self.assertEqual(lens_names, ["Evidence", "Impact"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "Source A")
        self.assertEqual(rows[0]["article_count"], 2)
        self.assertAlmostEqual(rows[0]["overall_avg"], 70.0)
        self.assertAlmostEqual(rows[0]["lens_means"]["Evidence"], 80.0)
        self.assertAlmostEqual(rows[0]["lens_means"]["Impact"], 55.0)

    def test_source_lens_rows_fall_back_to_legacy_high_score(self):
        rows, lens_names, coverage = _source_lens_rows(
            [
                {
                    "source": {"name": "Source B"},
                    "score": {"percent": 50.0, "lens_scores": {}},
                    "high_score": {"overall_percent": 50.0, "lens_scores": {"Evidence": 7.0}},
                },
                {
                    "source": {"name": "Source B"},
                    "score": {"percent": 60.0, "lens_scores": {}},
                    "high_score": {"overall_percent": 60.0, "lens_scores": {"Evidence": 8.0}},
                },
            ],
            {"Evidence": 10.0},
        )

        self.assertEqual(coverage, "high-score fallback")
        self.assertEqual(lens_names, ["Evidence"])
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["lens_means"]["Evidence"], 75.0)
        self.assertAlmostEqual(rows[0]["overall_avg"], 55.0)


if __name__ == "__main__":
    unittest.main()
