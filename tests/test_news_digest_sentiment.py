import importlib
import unittest

import dash


app = dash.Dash(__name__, use_pages=True, pages_folder="")
news_digest = importlib.import_module("src.pages.news_digest")


class NewsDigestSentimentTests(unittest.TestCase):
    def test_selected_article_text_prefers_summary_by_default(self):
        text, label = news_digest._selected_article_text(
            {"ai_summary": "Short summary", "body_text": "Long body text"},
            "summary",
        )

        self.assertEqual(text, "Short summary")
        self.assertEqual(label, "AI Summary")

    def test_selected_article_text_falls_back_to_body_when_summary_missing(self):
        text, label = news_digest._selected_article_text(
            {"ai_summary": "", "body_text": "Long body text"},
            "summary",
        )

        self.assertEqual(text, "Long body text")
        self.assertEqual(label, "Full Article Text")


if __name__ == "__main__":
    unittest.main()
