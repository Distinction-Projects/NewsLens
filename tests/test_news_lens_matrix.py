import unittest

import src.app  # noqa: F401
from src.pages.news_lens_matrix import _matrix_rows, _sorted_rows


class NewsLensMatrixTests(unittest.TestCase):
    def test_matrix_rows_prefer_full_score_lens_scores(self):
        rows, coverage = _matrix_rows(
            [
                {
                    "id": "article-1",
                    "title": "Alpha",
                    "source": {"name": "Source A"},
                    "published": "2026-04-05T00:00:00Z",
                    "score": {
                        "percent": 66.0,
                        "lens_scores": {
                            "Evidence": {"percent": 80.0},
                            "Impact": {"percent": 50.0},
                        },
                    },
                    "high_score": {"overall_percent": 66.0, "lens_scores": {"Evidence": 8.0}},
                }
            ],
            {"Evidence": 10.0, "Impact": 10.0},
        )

        self.assertEqual(coverage, "all scored articles")
        self.assertEqual(rows[0]["strongest_lens"], "Evidence")
        self.assertEqual(rows[0]["lens_scores"]["Impact"], 50.0)

    def test_matrix_rows_fall_back_to_legacy_scores(self):
        rows, coverage = _matrix_rows(
            [
                {
                    "id": "article-2",
                    "title": "Beta",
                    "source": {"name": "Source B"},
                    "published": "2026-04-05T00:00:00Z",
                    "score": {"percent": 58.0, "lens_scores": {}},
                    "high_score": {"overall_percent": 58.0, "lens_scores": {"Impact": 6.5}},
                }
            ],
            {"Impact": 10.0},
        )

        self.assertEqual(coverage, "high-score fallback")
        self.assertEqual(rows[0]["lens_scores"]["Impact"], 65.0)
        self.assertEqual(rows[0]["overall_percent"], 58.0)

    def test_sorted_rows_use_selected_lens_then_overall_score(self):
        rows = [
            {
                "title": "Alpha",
                "overall_percent": 50.0,
                "strongest_percent": 80.0,
                "lens_scores": {"Evidence": 70.0},
            },
            {
                "title": "Beta",
                "overall_percent": 65.0,
                "strongest_percent": 70.0,
                "lens_scores": {"Evidence": 70.0},
            },
            {
                "title": "Gamma",
                "overall_percent": 40.0,
                "strongest_percent": 60.0,
                "lens_scores": {"Evidence": 55.0},
            },
        ]

        ordered = _sorted_rows(rows, "Evidence")
        self.assertEqual([row["title"] for row in ordered], ["Beta", "Alpha", "Gamma"])


if __name__ == "__main__":
    unittest.main()
