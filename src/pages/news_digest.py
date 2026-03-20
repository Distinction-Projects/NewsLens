import json
from urllib.parse import urlencode

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, ctx, dcc, html, MATCH
from flask import current_app

from src.pages.news_page_utils import build_status_alert

try:
    from src.ml_sentiment import preprocess, prebuilt_model, predict_cached, predict_score_cached, vader_score
except ModuleNotFoundError:
    from ml_sentiment import preprocess, prebuilt_model, predict_cached, predict_score_cached, vader_score


dash.register_page(
    __name__,
    path="/news/digest",
    name="News Digest",
    title="Sentiment Analyzer | News Digest",
)


def _api_get(path: str, params: dict[str, str | int | None]) -> tuple[int, dict]:
    filtered = {key: value for key, value in params.items() if value not in (None, "", [])}
    query = urlencode(filtered, doseq=True)
    target = f"{path}?{query}" if query else path
    with current_app.test_client() as client:
        response = client.get(target)
    parsed = response.get_json(silent=True)
    if isinstance(parsed, dict):
        return response.status_code, parsed
    return response.status_code, {"status": "error", "error": response.get_data(as_text=True)}


def _article_component_id(kind: str, article_id: str, scope: str) -> dict[str, str]:
    return {"type": kind, "article_id": article_id, "scope": scope}


def _article_analysis_payload(payload: dict) -> dict[str, str | None]:
    scraped_raw = payload.get("scraped")
    scraped = scraped_raw if isinstance(scraped_raw, dict) else {}
    return {
        "title": payload.get("title") or "Untitled",
        "ai_summary": payload.get("ai_summary") or payload.get("summary"),
        "body_text": scraped.get("body_text"),
    }


def _analysis_controls(payload: dict, scope: str) -> html.Div:
    article_id = str(payload.get("id") or payload.get("link") or payload.get("title") or "article")
    source_options = [
        {"label": "AI Summary", "value": "summary"},
        {"label": "Full Article Text", "value": "body"},
    ]

    return html.Div(
        [
            html.Hr(className="my-3"),
            html.Div("Compare ML sentiment with the OpenAI article score:", className="fw-semibold mb-2"),
            dcc.Store(id=_article_component_id("news-analysis-data", article_id, scope), data=_article_analysis_payload(payload)),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Label("Text source", className="small"),
                            dcc.Dropdown(
                                id=_article_component_id("news-analysis-source", article_id, scope),
                                options=source_options,
                                value="summary",
                                clearable=False,
                            ),
                        ],
                        md=5,
                        className="mb-2",
                    ),
                    dbc.Col(
                        [
                            dbc.Label("Model", className="small"),
                            dcc.Dropdown(
                                id=_article_component_id("news-analysis-model", article_id, scope),
                                options=[
                                    {"label": "Naive Bayes", "value": "Naive Bayes"},
                                    {"label": "SVM", "value": "SVM"},
                                    {"label": "VADER", "value": "VADER"},
                                ],
                                value="Naive Bayes",
                                clearable=False,
                            ),
                        ],
                        md=4,
                        className="mb-2",
                    ),
                    dbc.Col(
                        [
                            dbc.Label("Action", className="small"),
                            dbc.Button(
                                "Run sentiment analysis",
                                id=_article_component_id("news-analysis-button", article_id, scope),
                                color="success",
                                className="w-100",
                            ),
                        ],
                        md=3,
                        className="mb-2",
                    ),
                ],
                className="g-2",
            ),
            html.Div(id=_article_component_id("news-analysis-result", article_id, scope), className="mt-2"),
        ]
    )


def _selected_article_text(data: dict | None, text_source: str | None) -> tuple[str | None, str]:
    payload = data if isinstance(data, dict) else {}
    summary_text = str(payload.get("ai_summary") or "").strip()
    body_text = str(payload.get("body_text") or "").strip()

    if text_source == "body":
        if body_text:
            return body_text, "Full Article Text"
        return None, "Full Article Text"

    if summary_text:
        return summary_text, "AI Summary"
    if body_text:
        return body_text, "Full Article Text"
    return None, "AI Summary"


def _run_article_sentiment(model_choice: str | None, text: str) -> tuple[str, float]:
    processed = preprocess(text)
    if not processed.strip():
        raise ValueError("The selected article text is empty after preprocessing.")

    if model_choice == "VADER":
        prediction = prebuilt_model([processed])[0]
        score = float(vader_score(processed))
    else:
        prediction = predict_cached([processed], model_choice or "Naive Bayes")[0]
        score = float(predict_score_cached([processed])[0])

    sentiment_map = {"positive": "Positive", "neutral": "Neutral", "negative": "Negative"}
    sentiment = sentiment_map.get(str(prediction).lower(), str(prediction))
    return sentiment, score


def _render_latest_card(payload: dict | None) -> dbc.Card:
    if not payload:
        return dbc.Card(dbc.CardBody(html.P("No matching article found.")), className="mb-3")

    source_raw = payload.get("source")
    source = source_raw if isinstance(source_raw, dict) else {}
    source_name = source.get("name") or source.get("id") or "Unknown source"
    published_at = payload.get("published_at") or payload.get("published") or "Unknown date"

    badges = []
    for tag in payload.get("tags", [])[:6]:
        badges.append(dbc.Badge(tag, color="secondary", className="me-1"))

    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(payload.get("title") or "Untitled", className="mb-2"),
                html.P(f"Source: {source_name}", className="mb-1"),
                html.P(f"Published (UTC): {published_at}", className="mb-1"),
                html.P(payload.get("ai_summary") or payload.get("summary") or "No summary available.", className="mb-2"),
                html.Div(badges, className="mb-2"),
                dbc.Button("Open Article", href=payload.get("link"), target="_blank", color="primary", size="sm")
                if payload.get("link")
                else html.Small("No link provided.", className="text-muted"),
                _analysis_controls(payload, scope="latest"),
            ]
        ),
        className="mb-3 shadow-sm",
    )


def _render_digest_rows(records: list[dict]) -> list:
    if not records:
        return [dbc.Alert("No records match these filters.", color="warning", className="mb-0")]

    rows = []
    for row in records:
        source_raw = row.get("source")
        source = source_raw if isinstance(source_raw, dict) else {}
        source_name = source.get("name") or source.get("id") or "Unknown source"
        published_at = row.get("published_at") or row.get("published") or "Unknown date"
        score_raw = row.get("score")
        score = score_raw if isinstance(score_raw, dict) else {}
        percent = score.get("percent")
        percent_text = f"{percent:.1f}%" if isinstance(percent, (int, float)) else "n/a"

        rows.append(
            dbc.ListGroupItem(
                [
                    html.Div(
                        [
                            html.Strong(row.get("title") or "Untitled"),
                            html.Span(f" ({source_name})", className="me-3"),
                        ],
                        className="mb-1",
                    ),
                    html.Div(
                        [
                            html.Span(f"Published: {published_at}", className="me-3"),
                            html.Span(f"Score: {percent_text}"),
                        ],
                        className="small text-muted mb-2",
                    ),
                    html.Div(
                        [dbc.Badge(tag, color="light", text_color="dark", className="me-1") for tag in row.get("tags", [])[:8]],
                        className="mb-2",
                    ),
                    html.Div(
                        dbc.Button("Read", href=row.get("link"), target="_blank", color="secondary", size="sm")
                        if row.get("link")
                        else html.Small("No link", className="text-muted")
                    ),
                    _analysis_controls(row, scope="list"),
                ]
            )
        )
    return [dbc.ListGroup(rows)]


layout = dbc.Container(
    [
        dcc.Interval(id="news-digest-load", interval=3000, n_intervals=0, max_intervals=1),
        dbc.Row(
            [
                dbc.Col(html.H3("News Digest", className="mb-3"), width=12),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Data mode"),
                        dcc.Dropdown(
                            id="news-filter-data-mode",
                            options=[
                                {"label": "Current", "value": "current"},
                                {"label": "Snapshot", "value": "snapshot"},
                            ],
                            value="current",
                            clearable=False,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Snapshot date (UTC)"),
                        dcc.Input(
                            id="news-filter-snapshot-date",
                            type="date",
                            className="form-control",
                            disabled=True,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Date (UTC YYYY-MM-DD)"),
                        dcc.Input(id="news-filter-date", type="text", placeholder="2026-03-02", className="form-control"),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Tag"),
                        dcc.Input(id="news-filter-tag", type="text", placeholder="OpenAI", className="form-control"),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Source"),
                        dcc.Input(id="news-filter-source", type="text", placeholder="PBS", className="form-control"),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Limit"),
                        dcc.Input(id="news-filter-limit", type="number", min=1, max=200, step=1, value=20, className="form-control"),
                    ],
                    md=1,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        html.Div(
                            [
                                dbc.Button("Apply", id="news-apply", color="primary", className="me-2"),
                                dbc.Button("Refresh", id="news-refresh", color="secondary"),
                            ]
                        ),
                    ],
                    md=1,
                ),
            ],
            className="mb-3",
        ),
        dbc.Row([dbc.Col(html.Div(id="news-digest-status"), width=12)]),
        dbc.Row(
            [
                dbc.Col([html.H5("Latest Match"), html.Div(id="news-latest-card")], lg=5),
                dbc.Col([html.H5("Digest Items"), html.Div(id="news-digest-list")], lg=7),
            ]
        ),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-digest-status", "children"),
    Output("news-latest-card", "children"),
    Output("news-digest-list", "children"),
    Input("news-digest-load", "n_intervals"),
    Input("news-apply", "n_clicks"),
    Input("news-refresh", "n_clicks"),
    State("news-filter-date", "value"),
    State("news-filter-tag", "value"),
    State("news-filter-source", "value"),
    State("news-filter-limit", "value"),
    State("news-filter-data-mode", "value"),
    State("news-filter-snapshot-date", "value"),
)
def load_news_digest(
    _interval,
    _apply_clicks,
    _refresh_clicks,
    date_filter,
    tag_filter,
    source_filter,
    limit_value,
    data_mode,
    snapshot_date,
):
    force_refresh = ctx.triggered_id == "news-refresh"
    snapshot_date_param = snapshot_date if data_mode == "snapshot" else None
    params = {
        "date": date_filter,
        "tag": tag_filter,
        "source": source_filter,
        "limit": limit_value or 20,
        "snapshot_date": snapshot_date_param,
        "refresh": "true" if force_refresh else None,
    }

    digest_status, digest_payload = _api_get("/api/news/digest", params)
    latest_status, latest_payload = _api_get(
        "/api/news/digest/latest",
        {
            "date": date_filter,
            "tag": tag_filter,
            "source": source_filter,
            "snapshot_date": snapshot_date_param,
            "refresh": "true" if force_refresh else None,
        },
    )

    if digest_status != 200:
        error_message = digest_payload.get("error") or json.dumps(digest_payload)
        return (
            dbc.Alert(f"Digest error ({digest_status}): {error_message}", color="danger"),
            _render_latest_card(None),
            [dbc.Alert("No data available.", color="warning")],
        )

    digest_meta = digest_payload.get("meta", {})
    latest_record = latest_payload.get("data") if latest_status == 200 else None
    records = digest_payload.get("data", [])

    status_component = build_status_alert(
        digest_meta,
        leading_parts=[f"Items returned: {digest_meta.get('returned_count', len(records))}"],
    )
    return status_component, _render_latest_card(latest_record), _render_digest_rows(records)


@callback(
    Output("news-filter-snapshot-date", "disabled"),
    Input("news-filter-data-mode", "value"),
)
def toggle_snapshot_date_input(data_mode):
    return data_mode != "snapshot"


@callback(
    Output({"type": "news-analysis-result", "article_id": MATCH, "scope": MATCH}, "children"),
    Input({"type": "news-analysis-button", "article_id": MATCH, "scope": MATCH}, "n_clicks"),
    State({"type": "news-analysis-source", "article_id": MATCH, "scope": MATCH}, "value"),
    State({"type": "news-analysis-model", "article_id": MATCH, "scope": MATCH}, "value"),
    State({"type": "news-analysis-data", "article_id": MATCH, "scope": MATCH}, "data"),
    prevent_initial_call=True,
)
def analyze_news_article(_n_clicks, text_source, model_choice, article_data):
    article_title = (article_data or {}).get("title") or "this article"
    selected_text, source_label = _selected_article_text(article_data, text_source)
    if not selected_text:
        return dbc.Alert(
            f"{source_label} is not available for {article_title}. Try the other text source.",
            color="warning",
            className="mb-0",
        )

    try:
        sentiment, score = _run_article_sentiment(model_choice, selected_text)
    except Exception as exc:  # noqa: BLE001
        return dbc.Alert(f"Sentiment analysis failed: {type(exc).__name__}: {exc}", color="danger", className="mb-0")

    card_color = "success" if sentiment == "Positive" else ("danger" if sentiment == "Negative" else "warning")
    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(f"Source analyzed: {source_label}", className="small text-muted mb-2"),
                html.P([html.Strong("Sentiment: "), sentiment], className="mb-1"),
                html.P([html.Strong("Emotional intensity score: "), f"{score:.3f}"], className="mb-1"),
                html.Small(f"Model: {model_choice}", className="text-muted"),
            ]
        ),
        color=card_color,
        outline=True,
    )
