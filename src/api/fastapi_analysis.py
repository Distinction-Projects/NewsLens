from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.NewsLens import (
    load_cached_metrics,
    predict_cached,
    predict_score_cached,
    prebuilt_model,
    preprocess,
    vader_score,
)
from src.services.database import persist_analysis_run


class TextAnalyzeRequest(BaseModel):
    text: str
    model: str = "Naive Bayes"


def _model_key(model_name: str) -> str:
    name = str(model_name or "").strip().lower()
    if name in ("naive bayes", "naivebayes", "nb", "multinomialnb"):
        return "naive bayes"
    if name in ("svm", "support vector machine", "support-vector-machine"):
        return "svm"
    if name == "vader":
        return "vader"
    raise ValueError(f"Unknown model name: {model_name}")


def _dataset_payload(dataset_key: str | None):
    metrics = load_cached_metrics(train_if_missing=False)
    datasets = metrics.get("datasets", {}) if isinstance(metrics, dict) else {}
    default_dataset = str(metrics.get("default_dataset", "train5")) if isinstance(metrics, dict) else "train5"
    key = str(dataset_key or default_dataset).strip().lower()
    dataset = datasets.get(key)
    if not isinstance(dataset, dict):
        raise ValueError(f"Unknown dataset: {dataset_key}")
    return metrics, key, dataset


def _macro_avg(values):
    if not isinstance(values, list) or not values:
        return None
    nums = [float(v) for v in values if isinstance(v, (int, float))]
    return sum(nums) / len(nums) if nums else None


def register_fastapi_analysis_endpoints(app: FastAPI) -> None:
    @app.get("/api/analysis/metrics")
    def get_analysis_metrics(dataset: str | None = Query(default=None)):
        try:
            metrics, dataset_key, dataset_payload = _dataset_payload(dataset)
        except ValueError as error:
            return JSONResponse(status_code=400, content={"status": "bad_request", "error": str(error), "data": None})
        except Exception as error:  # pragma: no cover
            return JSONResponse(status_code=500, content={"status": "error", "error": str(error), "data": None})

        models = dataset_payload.get("models", {}) if isinstance(dataset_payload, dict) else {}
        model_rows = []
        for name, row in models.items():
            if not isinstance(row, dict):
                continue
            model_rows.append(
                {
                    "key": name,
                    "accuracy": row.get("accuracy"),
                    "precision_macro": _macro_avg(row.get("precision")),
                    "recall_macro": _macro_avg(row.get("recall")),
                    "f1_macro": _macro_avg(row.get("f1")),
                    "confusion": row.get("confusion"),
                    "precision": row.get("precision"),
                    "recall": row.get("recall"),
                    "f1": row.get("f1"),
                }
            )

        return {
            "status": "ok",
            "error": None,
            "data": {
                "default_dataset": metrics.get("default_dataset"),
                "dataset": dataset_key,
                "display_name": dataset_payload.get("display_name"),
                "labels": dataset_payload.get("labels"),
                "models": model_rows,
            },
        }

    @app.post("/api/analysis/text")
    def post_text_analysis(payload: TextAnalyzeRequest):
        raw_text = str(payload.text or "").strip()
        if not raw_text:
            return JSONResponse(
                status_code=400,
                content={"status": "bad_request", "error": "Text is required.", "data": None},
            )

        try:
            processed = preprocess(raw_text)
            if not processed.strip():
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "bad_request",
                        "error": "No meaningful tokens remain after preprocessing.",
                        "data": None,
                    },
                )

            model_key = _model_key(payload.model)
            if model_key == "vader":
                sentiment = str(prebuilt_model([processed])[0])
                score = float(vader_score(processed))
                model_display = "VADER"
            else:
                sentiment = str(predict_cached([processed], payload.model)[0])
                score = float(predict_score_cached([processed])[0])
                model_display = "Naive Bayes" if model_key == "naive bayes" else "SVM"

            sentiment_display = {
                "positive": "Positive",
                "neutral": "Neutral",
                "negative": "Negative",
            }.get(sentiment.lower(), sentiment.title())

            storage = persist_analysis_run(
                model=model_display,
                sentiment=sentiment.lower(),
                score=score,
                input_text=raw_text,
                processed_text=processed,
                metadata={
                    "endpoint": "/api/analysis/text",
                    "model_key": model_key,
                },
            )

            return {
                "status": "ok",
                "error": None,
                "data": {
                    "model": model_display,
                    "model_key": model_key,
                    "sentiment": sentiment.lower(),
                    "sentiment_display": sentiment_display,
                    "score": score,
                    "processed_text": processed,
                    "storage": storage,
                },
            }
        except ValueError as error:
            return JSONResponse(status_code=400, content={"status": "bad_request", "error": str(error), "data": None})
        except Exception as error:  # pragma: no cover
            return JSONResponse(status_code=500, content={"status": "error", "error": str(error), "data": None})
