import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.fastapi_analysis import register_fastapi_analysis_endpoints


class FastApiAnalysisEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        register_fastapi_analysis_endpoints(app)
        cls.client = TestClient(app)

    @patch("src.api.fastapi_analysis.load_cached_metrics")
    def test_metrics_returns_dataset_models(self, mock_load_cached_metrics):
        mock_load_cached_metrics.return_value = {
            "default_dataset": "train5",
            "datasets": {
                "train5": {
                    "display_name": "Train5 Corpus",
                    "labels": ["negative", "neutral", "positive"],
                    "models": {
                        "naive bayes": {
                            "accuracy": 0.85,
                            "precision": [0.8, 0.81, 0.82],
                            "recall": [0.83, 0.84, 0.85],
                            "f1": [0.79, 0.8, 0.81],
                            "confusion": [[5, 1, 0], [1, 6, 1], [0, 1, 7]],
                        },
                        "svm": {
                            "accuracy": 0.9,
                            "precision": [0.88, 0.89, 0.9],
                            "recall": [0.9, 0.91, 0.92],
                            "f1": [0.87, 0.88, 0.89],
                            "confusion": [[6, 0, 0], [0, 7, 1], [0, 1, 8]],
                        },
                    },
                }
            },
        }

        response = self.client.get("/api/analysis/metrics")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["dataset"], "train5")
        self.assertEqual(payload["data"]["display_name"], "Train5 Corpus")
        self.assertEqual(len(payload["data"]["models"]), 2)
        model_keys = {row["key"] for row in payload["data"]["models"]}
        self.assertIn("naive bayes", model_keys)
        self.assertIn("svm", model_keys)

    @patch("src.api.fastapi_analysis.load_cached_metrics")
    def test_metrics_bad_dataset_returns_400(self, mock_load_cached_metrics):
        mock_load_cached_metrics.return_value = {
            "default_dataset": "train5",
            "datasets": {"train5": {"display_name": "Train5 Corpus", "labels": [], "models": {}}},
        }

        response = self.client.get("/api/analysis/metrics?dataset=unknown")
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["status"], "bad_request")

    @patch("src.api.fastapi_analysis.predict_score_cached")
    @patch("src.api.fastapi_analysis.predict_cached")
    @patch("src.api.fastapi_analysis.preprocess")
    @patch("src.api.fastapi_analysis.persist_analysis_run")
    def test_text_analysis_nb(self, mock_persist_analysis_run, mock_preprocess, mock_predict_cached, mock_predict_score_cached):
        mock_preprocess.return_value = "hello world"
        mock_predict_cached.return_value = ["positive"]
        mock_predict_score_cached.return_value = [0.42]
        mock_persist_analysis_run.return_value = {"status": "saved", "saved": True, "id": 101, "error": None}

        response = self.client.post("/api/analysis/text", json={"text": "Hello world", "model": "Naive Bayes"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["model_key"], "naive bayes")
        self.assertEqual(payload["data"]["sentiment"], "positive")
        self.assertAlmostEqual(payload["data"]["score"], 0.42)
        self.assertEqual(payload["data"]["storage"]["status"], "saved")
        mock_persist_analysis_run.assert_called_once()

    @patch("src.api.fastapi_analysis.vader_score")
    @patch("src.api.fastapi_analysis.prebuilt_model")
    @patch("src.api.fastapi_analysis.preprocess")
    @patch("src.api.fastapi_analysis.persist_analysis_run")
    def test_text_analysis_vader(self, mock_persist_analysis_run, mock_preprocess, mock_prebuilt_model, mock_vader_score):
        mock_preprocess.return_value = "sample text"
        mock_prebuilt_model.return_value = ["neutral"]
        mock_vader_score.return_value = 0.05
        mock_persist_analysis_run.return_value = {"status": "unconfigured", "saved": False, "error": None}

        response = self.client.post("/api/analysis/text", json={"text": "Sample text", "model": "VADER"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["model_key"], "vader")
        self.assertEqual(payload["data"]["sentiment"], "neutral")
        self.assertEqual(payload["data"]["storage"]["status"], "unconfigured")
        mock_persist_analysis_run.assert_called_once()

    @patch("src.api.fastapi_analysis.persist_analysis_run")
    def test_text_analysis_empty_text_returns_400(self, mock_persist_analysis_run):
        response = self.client.post("/api/analysis/text", json={"text": "   ", "model": "SVM"})
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["status"], "bad_request")
        mock_persist_analysis_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
