import unittest

import src.app  # noqa: F401
from src.pages.news_source_tag_matrix import _source_tag_counts, _top_labels


class NewsSourceTagMatrixTests(unittest.TestCase):
    def test_top_labels_rank_sources_and_tags_by_total_count(self):
        source_labels, tag_labels = _top_labels(
            [
                {"source": "Source A", "tag": "Policy", "count": 5},
                {"source": "Source A", "tag": "Economy", "count": 2},
                {"source": "Source B", "tag": "Policy", "count": 6},
                {"source": "Source C", "tag": "AI", "count": 4},
            ],
            top_sources=2,
            top_tags=2,
        )

        self.assertEqual(source_labels, ["Source A", "Source B"])
        self.assertEqual(tag_labels, ["Policy", "AI"])

    def test_source_tag_counts_filter_and_sort(self):
        rows = _source_tag_counts(
            [
                {"source": "Source A", "tag": "Policy", "count": 5},
                {"source": "Source A", "tag": "Economy", "count": 2},
                {"source": "Source A", "tag": "AI", "count": 7},
                {"source": "Source B", "tag": "Policy", "count": 10},
            ],
            source_name="Source A",
            top_n=2,
        )

        self.assertEqual(rows, [("AI", 7), ("Policy", 5)])


if __name__ == "__main__":
    unittest.main()
