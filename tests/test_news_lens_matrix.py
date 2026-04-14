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
                }
            ],
            {"Evidence": 10.0, "Impact": 10.0},
        )

        self.assertEqual(coverage, "all scored articles")
        self.assertEqual(rows[0]["strongest_lens"], "Evidence")
        self.assertEqual(rows[0]["lens_scores"]["Impact"], 50.0)

    def test_matrix_rows_skip_articles_without_full_lens_scores(self):
        rows, coverage = _matrix_rows(
            [
                {
                    "id": "article-2",
                    "title": "Beta",
                    "source": {"name": "Source B"},
                    "published": "2026-04-05T00:00:00Z",
                    "score": {"percent": 58.0, "lens_scores": {}},
                }
            ],
            {"Impact": 10.0},
        )

        self.assertEqual(coverage, "no lens data")
        self.assertEqual(rows, [])

    def test_sorted_rows_prioritize_selected_lens_separation_gap(self):
        rows = [
            {
                "title": "Alpha",
                "strongest_percent": 70.0,
                "lens_scores": {"Evidence": 70.0, "Impact": 69.0},
            },
            {
                "title": "Beta",
                "strongest_percent": 68.0,
                "lens_scores": {"Evidence": 68.0, "Impact": 20.0},
            },
            {
                "title": "Gamma",
                "strongest_percent": 70.0,
                "lens_scores": {"Evidence": 70.0, "Impact": 40.0},
            },
        ]

        ordered = _sorted_rows(rows, "Evidence")
        self.assertEqual([row["title"] for row in ordered], ["Beta", "Gamma", "Alpha"])


if __name__ == "__main__":
    unittest.main()
