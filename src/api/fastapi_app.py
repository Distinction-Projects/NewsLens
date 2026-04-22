from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.api.fastapi_analysis import register_fastapi_analysis_endpoints
from src.api.fastapi_news import register_fastapi_news_endpoints
from src.services.database import database_health_snapshot


def _parse_cors_origins(raw: str | None) -> list[str]:
    if raw is None:
        return ["http://localhost:3000", "http://127.0.0.1:3000"]
    origins = [value.strip() for value in raw.split(",")]
    return [value for value in origins if value]


def create_fastapi_app() -> FastAPI:
    app = FastAPI(title="NewsLens API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_parse_cors_origins(os.getenv("NEWS_API_CORS_ORIGINS")),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_fastapi_news_endpoints(app)
    register_fastapi_analysis_endpoints(app)

    @app.get("/health/database")
    def database_health():
        snapshot = database_health_snapshot()
        if snapshot.get("status") == "error":
            return JSONResponse(
                status_code=503,
                content={"status": "error", "error": snapshot.get("error"), "data": snapshot},
            )
        return {"status": "ok", "error": None, "data": snapshot}

    return app


app = create_fastapi_app()
