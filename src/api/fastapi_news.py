from __future__ import annotations

from typing import Callable

from fastapi import FastAPI, Query, Response
from fastapi.responses import JSONResponse

from src.api.news_controller import ControllerResponse, NewsController
from src.api.news_schemas import NewsApiEnvelope
from src.services.rss_digest import RssDigestClient


def _to_fastapi_response(controller_response: ControllerResponse):
    if controller_response.content_type == "application/json":
        return JSONResponse(
            status_code=controller_response.status_code,
            content=controller_response.body,
            headers=controller_response.headers or None,
        )

    return Response(
        status_code=controller_response.status_code,
        content=str(controller_response.body),
        media_type=controller_response.content_type,
        headers=controller_response.headers or None,
    )


def register_fastapi_news_endpoints(
    app: FastAPI,
    *,
    controller_factory: Callable[[], NewsController] | None = None,
) -> None:
    factory = controller_factory or (lambda: NewsController(RssDigestClient()))
    controller = factory()

    @app.get("/api/news/digest", response_model=NewsApiEnvelope)
    def get_news_digest(
        refresh: str | None = Query(default=None),
        date: str | None = Query(default=None),
        tag: str | None = Query(default=None),
        source: str | None = Query(default=None),
        limit: str | None = Query(default=None),
        snapshot_date: str | None = Query(default=None),
    ):
        response = controller.get_digest(
            refresh=refresh,
            date=date,
            tag=tag,
            source=source,
            limit=limit,
            snapshot_date=snapshot_date,
        )
        return _to_fastapi_response(response)

    @app.get("/api/news/digest/latest", response_model=NewsApiEnvelope)
    def get_latest_news_digest(
        refresh: str | None = Query(default=None),
        date: str | None = Query(default=None),
        tag: str | None = Query(default=None),
        source: str | None = Query(default=None),
        snapshot_date: str | None = Query(default=None),
    ):
        response = controller.get_latest_digest(
            refresh=refresh,
            date=date,
            tag=tag,
            source=source,
            snapshot_date=snapshot_date,
        )
        return _to_fastapi_response(response)

    @app.get("/api/news/stats", response_model=NewsApiEnvelope)
    def get_news_stats(
        refresh: str | None = Query(default=None),
        snapshot_date: str | None = Query(default=None),
    ):
        response = controller.get_stats(
            refresh=refresh,
            snapshot_date=snapshot_date,
        )
        return _to_fastapi_response(response)

    @app.get("/api/news/upstream", response_model=NewsApiEnvelope)
    def get_news_upstream(
        refresh: str | None = Query(default=None),
        snapshot_date: str | None = Query(default=None),
    ):
        response = controller.get_upstream(
            refresh=refresh,
            snapshot_date=snapshot_date,
        )
        return _to_fastapi_response(response)

    @app.get("/api/news/export")
    def export_news_artifact(
        refresh: str | None = Query(default=None),
        artifact: str | None = Query(default=None),
        format: str | None = Query(default=None),
        snapshot_date: str | None = Query(default=None),
    ):
        response = controller.export_artifact(
            refresh=refresh,
            artifact=artifact,
            export_format=format,
            snapshot_date=snapshot_date,
        )
        return _to_fastapi_response(response)

    @app.get("/health/news-freshness", response_model=NewsApiEnvelope)
    def news_freshness_health():
        response = controller.get_news_freshness()
        return _to_fastapi_response(response)
