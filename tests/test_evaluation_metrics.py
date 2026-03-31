import unittest

from src.NewsLens import _build_dataset_metrics, load_cached_metrics


class EvaluationMetricsTests(unittest.TestCase):
    def test_news_dataset_includes_openai_metrics(self):
        metrics = _build_dataset_metrics("news", k=5)

        self.assertEqual(metrics["labels"], ["negative", "neutral", "positive"])
        self.assertIn("openai", metrics["models"])
        self.assertEqual(metrics["models"]["openai"]["accuracy"], 1.0)

    def test_cached_metrics_include_train5_and_news_datasets(self):
        metrics_cache = load_cached_metrics()

        self.assertEqual(metrics_cache["default_dataset"], "train5")
        self.assertIn("train5", metrics_cache["datasets"])
        self.assertIn("news", metrics_cache["datasets"])
        self.assertNotIn("openai", metrics_cache["datasets"]["train5"]["models"])
        self.assertIn("openai", metrics_cache["datasets"]["news"]["models"])


if __name__ == "__main__":
    unittest.main()
