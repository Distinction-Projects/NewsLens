import unittest

import src.app  # noqa: F401
from src.pages.news_lens_stability import _lens_stability_rows


class NewsLensStabilityTests(unittest.TestCase):
    def test_lens_stability_rows_prefer_full_scores(self):
        rows, coverage = _lens_stability_rows(
            [
                {
                    "source": {"name": "Source A"},
                    "score": {"lens_scores": {"Evidence": {"percent": 80.0}, "Impact": {"percent": 50.0}}},
                },
                {
                    "source": {"name": "Source B"},
                    "score": {"lens_scores": {"Evidence": {"percent": 60.0}, "Impact": {"percent": 70.0}}},
                },
            ],
            {"Evidence": 10.0, "Impact": 10.0},
        )

        self.assertEqual(coverage, "all scored articles")
        self.assertEqual(len(rows), 2)
        by_lens = {row["lens"]: row for row in rows}
        self.assertAlmostEqual(by_lens["Evidence"]["mean"], 70.0)
        self.assertAlmostEqual(by_lens["Evidence"]["range"], 20.0)
        self.assertAlmostEqual(by_lens["Impact"]["mean"], 60.0)
        self.assertAlmostEqual(by_lens["Impact"]["source_gap"], 20.0)

    def test_lens_stability_rows_skip_articles_without_full_lens_scores(self):
        rows, coverage = _lens_stability_rows(
            [
                {
                    "source": {"name": "Source A"},
                    "score": {"lens_scores": {}},
                },
                {
                    "source": {"name": "Source B"},
                    "score": {"lens_scores": {}},
                },
            ],
            {"Evidence": 10.0},
        )

        self.assertEqual(coverage, "no lens data")
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
