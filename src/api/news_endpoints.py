from __future__ import annotations

from flask import jsonify, make_response, request

from src.api.news_controller import ControllerResponse, NewsController
from src.services.rss_digest import RssDigestClient


def _to_flask_response(response: ControllerResponse):
    if response.content_type == "application/json":
        flask_response = jsonify(response.body)
        for header_name, header_value in response.headers.items():
            flask_response.headers[header_name] = header_value
        return flask_response, response.status_code

    flask_response = make_response(str(response.body), response.status_code)
    flask_response.headers["Content-Type"] = response.content_type
    for header_name, header_value in response.headers.items():
        flask_response.headers[header_name] = header_value
    return flask_response, response.status_code


def register_news_endpoints(server) -> None:
    controller = NewsController(RssDigestClient())

    @server.get("/api/news/digest")
    def get_news_digest():
        response = controller.get_digest(
            refresh=request.args.get("refresh"),
            date=request.args.get("date"),
            tag=request.args.get("tag"),
            source=request.args.get("source"),
            limit=request.args.get("limit"),
            snapshot_date=request.args.get("snapshot_date"),
        )
        return _to_flask_response(response)

    @server.get("/api/news/digest/latest")
    def get_latest_news_digest():
        response = controller.get_latest_digest(
            refresh=request.args.get("refresh"),
            date=request.args.get("date"),
            tag=request.args.get("tag"),
            source=request.args.get("source"),
            snapshot_date=request.args.get("snapshot_date"),
        )
        return _to_flask_response(response)

    @server.get("/api/news/stats")
    def get_news_stats():
        response = controller.get_stats(
            refresh=request.args.get("refresh"),
            snapshot_date=request.args.get("snapshot_date"),
        )
        return _to_flask_response(response)

    @server.get("/api/news/upstream")
    def get_news_upstream():
        response = controller.get_upstream(
            refresh=request.args.get("refresh"),
            snapshot_date=request.args.get("snapshot_date"),
        )
        return _to_flask_response(response)

    @server.get("/api/news/export")
    def export_news_artifact():
        response = controller.export_artifact(
            refresh=request.args.get("refresh"),
            artifact=request.args.get("artifact"),
            export_format=request.args.get("format"),
            snapshot_date=request.args.get("snapshot_date"),
        )
        return _to_flask_response(response)

    @server.get("/health/news-freshness")
    def news_freshness_health():
        response = controller.get_news_freshness()
        return _to_flask_response(response)
