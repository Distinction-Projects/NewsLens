import unittest

import src.app  # noqa: F401
from src.pages.news_high_score_lenses import _article_rows


class NewsLensExplorerTests(unittest.TestCase):
    def test_article_rows_prefer_full_score_lens_scores(self):
        rows, coverage = _article_rows(
            [
                {
                    "title": "Alpha",
                    "published": "2026-04-05T00:00:00Z",
                    "source": {"name": "Source A"},
                    "score": {
                        "percent": 62.5,
                        "lens_scores": {
                            "Evidence": {
                                "value": 7.5,
                                "max_value": 10.0,
                                "percent": 75.0,
                                "rubric_count": 1,
                            },
                            "Impact": {
                                "value": 5.0,
                                "max_value": 10.0,
                                "percent": 50.0,
                                "rubric_count": 1,
                            },
                        },
                    },
                    "high_score": {
                        "overall_percent": 62.5,
                        "lens_scores": {
                            "Evidence": 7.5,
                        },
                    },
                }
            ],
            {"Evidence": 10.0, "Impact": 10.0},
        )

        self.assertEqual(coverage, "all scored articles")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["overall_percent"], 62.5)
        self.assertEqual(rows[0]["strongest_lens"], "Evidence")
        self.assertEqual(rows[0]["lens_scores"]["Impact"], 50.0)

    def test_article_rows_fall_back_to_legacy_high_score_scores(self):
        rows, coverage = _article_rows(
            [
                {
                    "title": "Beta",
                    "published": "2026-04-05T00:00:00Z",
                    "source": {"name": "Source B"},
                    "score": {"percent": 58.0, "lens_scores": {}},
                    "high_score": {
                        "overall_percent": 58.0,
                        "lens_scores": {
                            "Evidence": 7.5,
                        },
                    },
                }
            ],
            {"Evidence": 10.0},
        )

        self.assertEqual(coverage, "high-score fallback")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["lens_scores"]["Evidence"], 75.0)
        self.assertEqual(rows[0]["strongest_percent"], 75.0)


if __name__ == "__main__":
    unittest.main()
