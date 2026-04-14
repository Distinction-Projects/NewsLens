from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/source-differentiation",
    name="News Source Differentiation",
    title="NewsLens | News Source Differentiation",
)


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(title=title, template="plotly_white", margin={"l": 30, "r": 20, "t": 60, "b": 40})
    return figure


def _source_count_rows(source_counts: dict) -> list[tuple[str, int]]:
    if not isinstance(source_counts, dict):
        return []
    return sorted(((str(name), int(count)) for name, count in source_counts.items()), key=lambda item: (-item[1], item[0].lower()))


def _source_count_figure(source_counts: dict) -> go.Figure:
    rows = _source_count_rows(source_counts)
    if not rows:
        return _empty_figure("Articles by Source")
    figure = go.Figure(data=[go.Bar(x=[row[0] for row in rows], y=[row[1] for row in rows], marker_color="#fd7e14")])
    figure.update_layout(title="Articles by Source in Differentiation Analysis", template="plotly_white")
    return figure


def _classification_figure(classification: dict) -> go.Figure:
    if not isinstance(classification, dict):
        return _empty_figure("Classification Accuracy")
    accuracy = classification.get("accuracy")
    baseline = classification.get("baseline_accuracy")
    if not isinstance(accuracy, (int, float)) and not isinstance(baseline, (int, float)):
        return _empty_figure("Classification Accuracy")
    figure = go.Figure(
        data=[
            go.Bar(
                x=["Classifier", "Baseline"],
                y=[
                    float(accuracy) * 100.0 if isinstance(accuracy, (int, float)) else 0.0,
                    float(baseline) * 100.0 if isinstance(baseline, (int, float)) else 0.0,
                ],
                marker_color=["#198754", "#6c757d"],
            )
        ]
    )
    figure.update_layout(title="Source Classification Accuracy (%)", template="plotly_white", yaxis={"range": [0, 100]})
    return figure


def _summary_cards(source_diff: dict) -> list:
    cards = [
        ("Status", source_diff.get("status", "n/a")),
        ("Articles", source_diff.get("n_articles", 0)),
        ("Sources", source_diff.get("n_sources", 0)),
        ("Lenses", source_diff.get("n_lenses", 0)),
        ("Permutations", source_diff.get("permutations", 0)),
    ]
    return [
        dbc.Col(
            dbc.Card(
                dbc.CardBody([html.P(label, className="text-muted mb-1"), html.H4(str(value), className="mb-0")]),
                className="shadow-sm",
            ),
            md=4,
            lg=2,
            className="mb-3",
        )
        for label, value in cards
    ]


def _select_source_differentiation(data: dict) -> tuple[dict, str]:
    if not isinstance(data, dict):
        return {}, "missing"

    derived = data.get("derived") if isinstance(data.get("derived"), dict) else {}
    derived_source_diff = derived.get("source_differentiation")
    if isinstance(derived_source_diff, dict) and derived_source_diff:
        return derived_source_diff, "derived"

    analysis = data.get("analysis") if isinstance(data.get("analysis"), dict) else {}
    upstream = analysis.get("source_differentiation")
    if isinstance(upstream, dict) and upstream:
        return upstream, "upstream"

    return {}, "missing"


def _metric_table(title: str, rows: list[tuple[str, object]]):
    body_rows = [html.Tr([html.Td(label), html.Td(str(value))]) for label, value in rows]
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(title, className="card-title"),
                dbc.Table(
                    [html.Tbody(body_rows)],
                    bordered=True,
                    striped=True,
                    hover=True,
                    responsive=True,
                    size="sm",
                    class_name="mb-0",
                ),
            ]
        ),
        className="shadow-sm h-100",
    )


def _source_count_table(source_counts: dict):
    rows = _source_count_rows(source_counts)
    if not rows:
        return dbc.Alert("No source counts are available.", color="warning", className="mb-0")
    table_rows = [html.Tr([html.Td(name), html.Td(count)]) for name, count in rows]
    return dbc.Table(
        [html.Thead(html.Tr([html.Th("Source"), html.Th("Articles")])), html.Tbody(table_rows)],
        bordered=True,
        striped=True,
        hover=True,
        responsive=True,
        size="sm",
    )


layout = dbc.Container(
    [
        dcc.Interval(id="news-source-diff-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Source Differentiation", className="mb-2"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    html.P(
                        "These statistics estimate how separable sources are in lens-score space. "
                        "Backend-derived source differentiation is preferred, with upstream analysis as fallback.",
                        className="text-muted",
                    ),
                    width=12,
                )
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Data mode"),
                        dcc.Dropdown(
                            id="news-source-diff-mode",
                            options=[
                                {"label": "Current", "value": "current"},
                                {"label": "Snapshot", "value": "snapshot"},
                            ],
                            value="current",
                            clearable=False,
                        ),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        dbc.Label("Snapshot date (UTC)"),
                        dcc.Input(id="news-source-diff-snapshot-date", type="date", className="form-control", disabled=True),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-source-diff-refresh", color="secondary"),
                    ],
                    md=2,
                ),
                dbc.Col(html.Div(id="news-source-diff-status"), md=4),
            ],
            className="mb-3",
        ),
        dbc.Row(id="news-source-diff-cards"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-source-diff-count-graph"), lg=7, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-source-diff-classification-graph"), lg=5, className="mb-3"),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(html.Div(id="news-source-diff-multivariate"), lg=4, className="mb-3"),
                dbc.Col(html.Div(id="news-source-diff-classification"), lg=4, className="mb-3"),
                dbc.Col(html.Div(id="news-source-diff-count-table"), lg=4, className="mb-3"),
            ]
        ),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-source-diff-status", "children"),
    Output("news-source-diff-cards", "children"),
    Output("news-source-diff-count-graph", "figure"),
    Output("news-source-diff-classification-graph", "figure"),
    Output("news-source-diff-multivariate", "children"),
    Output("news-source-diff-classification", "children"),
    Output("news-source-diff-count-table", "children"),
    Input("news-source-diff-load", "n_intervals"),
    Input("news-source-diff-refresh", "n_clicks"),
    State("news-source-diff-mode", "value"),
    State("news-source-diff-snapshot-date", "value"),
)
def load_news_source_differentiation(_load_tick, _refresh_clicks, data_mode, snapshot_date):
    force_refresh = ctx.triggered_id == "news-source-diff-refresh"
    status_code, payload = api_get(
        "/api/news/stats",
        {
            "snapshot_date": snapshot_param(data_mode, snapshot_date),
            "refresh": "true" if force_refresh else None,
        },
    )

    if status_code != 200:
        error = payload.get("error", "Unknown error")
        empty = _empty_figure("No data")
        alert = dbc.Alert(f"Stats error ({status_code}): {error}", color="danger")
        return alert, _summary_cards({}), empty, empty, alert, alert, alert

    meta = payload.get("meta", {})
    data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
    source_diff, source_mode = _select_source_differentiation(data)
    classification = source_diff.get("classification", {}) if isinstance(source_diff, dict) else {}
    multivariate = source_diff.get("multivariate", {}) if isinstance(source_diff, dict) else {}
    source_counts = source_diff.get("source_counts", {}) if isinstance(source_diff, dict) else {}

    multivariate_rows = [
        ("F statistic", f"{float(multivariate.get('f_stat')):.4f}" if isinstance(multivariate.get("f_stat"), (int, float)) else "n/a"),
        ("R squared", f"{float(multivariate.get('r_squared')):.4f}" if isinstance(multivariate.get("r_squared"), (int, float)) else "n/a"),
        ("Between df", multivariate.get("df_between", "n/a")),
        ("Within df", multivariate.get("df_within", "n/a")),
        ("Permutation p", f"{float(multivariate.get('p_perm')):.4f}" if isinstance(multivariate.get("p_perm"), (int, float)) else "n/a"),
    ]
    classification_rows = [
        ("Accuracy", f"{float(classification.get('accuracy')) * 100.0:.1f}%" if isinstance(classification.get("accuracy"), (int, float)) else "n/a"),
        (
            "Baseline accuracy",
            f"{float(classification.get('baseline_accuracy')) * 100.0:.1f}%"
            if isinstance(classification.get("baseline_accuracy"), (int, float))
            else "n/a",
        ),
        ("Evaluated", classification.get("evaluated", "n/a")),
        ("Total", classification.get("total", "n/a")),
        ("Permutation p", f"{float(classification.get('p_perm')):.4f}" if isinstance(classification.get("p_perm"), (int, float)) else "n/a"),
    ]

    return (
        build_status_alert(
            meta,
            leading_parts=[
                f"Analysis status: {source_diff.get('status', 'missing')}",
                f"Source: {source_mode}",
            ],
        ),
        _summary_cards(source_diff),
        _source_count_figure(source_counts),
        _classification_figure(classification),
        _metric_table("Multivariate Separation", multivariate_rows),
        _metric_table("Classification Check", classification_rows),
        dbc.Card(dbc.CardBody([html.H5("Source Counts", className="card-title"), _source_count_table(source_counts)]), className="shadow-sm h-100"),
    )


@callback(
    Output("news-source-diff-snapshot-date", "disabled"),
    Input("news-source-diff-mode", "value"),
)
def toggle_source_diff_snapshot_input(data_mode):
    return data_mode != "snapshot"
