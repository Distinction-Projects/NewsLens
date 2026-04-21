import unittest

import dash_bootstrap_components as dbc
from dash import html

from src.pages.news_page_utils import build_news_intro


class NewsPageUtilsTests(unittest.TestCase):
    def test_build_news_intro_structure_and_classes(self):
        intro_row = build_news_intro("Summary text.")

        self.assertIsInstance(intro_row, dbc.Row)
        self.assertEqual(intro_row.className, "mb-3")
        self.assertEqual(len(intro_row.children), 1)

        intro_col = intro_row.children[0]
        self.assertIsInstance(intro_col, dbc.Col)

        accordion = intro_col.children
        self.assertIsInstance(accordion, dbc.Accordion)
        self.assertEqual(accordion.className, "news-page-intro")
        self.assertTrue(accordion.start_collapsed)
        self.assertEqual(len(accordion.children), 1)

        item = accordion.children[0]
        self.assertIsInstance(item, dbc.AccordionItem)
        self.assertEqual(item.title, "What this page does")

    def test_build_news_intro_renders_text_verbatim(self):
        summary = "Inspect lens-space separation by source."
        intro_row = build_news_intro(summary)

        paragraph = intro_row.children[0].children.children[0].children
        self.assertIsInstance(paragraph, html.P)
        self.assertEqual(paragraph.children, summary)


if __name__ == "__main__":
    unittest.main()
