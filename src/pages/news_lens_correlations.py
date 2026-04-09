from __future__ import annotations

import math

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/lens-correlations",
    name="News Lens Correlations",
    title="NewsLens | News Lens Correlations",
)


MATRIX_OPTIONS = [
    {"label": "Correlation (Raw)", "value": "corr_raw"},
    {"label": "Correlation (Normalized)", "value": "corr_norm"},
    {"label": "Covariance (Raw)", "value": "cov_raw"},
    {"label": "Covariance (Normalized)", "value": "cov_norm"},
    {"label": "Pairwise Counts", "value": "pairwise"},
]

MATRIX_LABELS = {
    "corr_raw": "Correlation (Raw)",
    "corr_norm": "Correlation (Normalized)",
    "cov_raw": "Covariance (Raw)",
    "cov_norm": "Covariance (Normalized)",
    "pairwise": "Pairwise Counts",
}


def _select_lens_correlations(data: dict) -> tuple[dict, str]:
    if not isinstance(data, dict):
        return {}, "missing"

    derived = data.get("derived")
    derived_corr = derived.get("lens_correlations") if isinstance(derived, dict) else None
    if isinstance(derived_corr, dict):
        return derived_corr, "derived"

    analysis = data.get("analysis")
    upstream = analysis.get("lens_correlations") if isinstance(analysis, dict) else None
    if isinstance(upstream, dict) and isinstance(upstream.get("lenses"), list) and upstream.get("lenses"):
        return upstream, "upstream"

    return {}, "missing"


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(title=title, template="plotly_white", margin={"l": 40, "r": 20, "t": 60, "b": 40})
    return figure


def _normalized_square_matrix(lenses: list[str], matrix: object) -> list[list[float | None]]:
    target = len(lenses)
    if not isinstance(matrix, list) or target <= 0:
        return []

    normalized: list[list[float | None]] = []
    for row in matrix[:target]:
        row_values: list[float | None] = []
        values = row if isinstance(row, list) else []
        for value in values[:target]:
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                row_values.append(float(value))
            else:
                row_values.append(None)
        if len(row_values) < target:
            row_values.extend([None] * (target - len(row_values)))
        normalized.append(row_values)
    while len(normalized) < target:
        normalized.append([None] * target)
    return normalized


def _matrix_payload(lens_correlations: dict, matrix_key: str) -> tuple[list[str], list[list[float | None]], str]:
    lenses = lens_correlations.get("lenses", []) if isinstance(lens_correlations, dict) else []
    lens_names = [str(name) for name in lenses if isinstance(name, str) and name.strip()]

    correlation = lens_correlations.get("correlation", {}) if isinstance(lens_correlations, dict) else {}
    covariance = lens_correlations.get("covariance", {}) if isinstance(lens_correlations, dict) else {}
    matrix_lookup = {
        "corr_raw": correlation.get("raw"),
        "corr_norm": correlation.get("normalized"),
        "cov_raw": covariance.get("raw"),
        "cov_norm": covariance.get("normalized"),
        "pairwise": lens_correlations.get("pairwise_counts"),
    }
    matrix = _normalized_square_matrix(lens_names, matrix_lookup.get(matrix_key))
    return lens_names, matrix, MATRIX_LABELS.get(matrix_key, "Matrix")


def _pair_rows(
    lenses: list[str],
    matrix: list[list[float | None]],
    matrix_key: str,
) -> list[tuple[str, str, float]]:
    rows: list[tuple[str, str, float]] = []
    for row_index, left_lens in enumerate(lenses):
        for col_index in range(row_index + 1, len(lenses)):
            value = matrix[row_index][col_index]
            if not isinstance(value, (int, float)):
                continue
            rows.append((left_lens, lenses[col_index], float(value)))

    if matrix_key == "pairwise":
        return sorted(rows, key=lambda row: row[2], reverse=True)
    return sorted(rows, key=lambda row: (abs(row[2]), row[2]), reverse=True)


def _pair_rows_from_backend(lens_correlations: dict, matrix_key: str) -> list[tuple[str, str, float]] | None:
    pair_rankings = lens_correlations.get("pair_rankings") if isinstance(lens_correlations, dict) else None
    if not isinstance(pair_rankings, dict):
        return None
    ranking_rows = pair_rankings.get(matrix_key)
    if not isinstance(ranking_rows, list):
        return None

    rows: list[tuple[str, str, float]] = []
    for row in ranking_rows:
        if not isinstance(row, dict):
            continue
        lens_a = row.get("lens_a")
        lens_b = row.get("lens_b")
        value = row.get("value")
        if isinstance(lens_a, str) and lens_a.strip() and isinstance(lens_b, str) and lens_b.strip() and isinstance(value, (int, float)):
            rows.append((lens_a, lens_b, float(value)))
    return rows


def _matrix_summary_from_backend(lens_correlations: dict, matrix_key: str) -> dict | None:
    summary_by_matrix = lens_correlations.get("summary_by_matrix") if isinstance(lens_correlations, dict) else None
    if not isinstance(summary_by_matrix, dict):
        return None
    matrix_summary = summary_by_matrix.get(matrix_key)
    if not isinstance(matrix_summary, dict):
        return None
    return matrix_summary


def _summary_cards(
    lenses: list[str],
    pair_rows: list[tuple[str, str, float]],
    matrix_label: str,
    matrix_summary: dict | None = None,
) -> list:
    summary = matrix_summary if isinstance(matrix_summary, dict) else {}
    strongest_pair = str(summary.get("strongest_pair")) if isinstance(summary.get("strongest_pair"), str) else (
        f"{pair_rows[0][0]} / {pair_rows[0][1]}" if pair_rows else "n/a"
    )
    strongest_value_raw = summary.get("strongest_value")
    if isinstance(strongest_value_raw, (int, float)):
        strongest_value = f"{float(strongest_value_raw):.4f}"
    else:
        strongest_value = f"{pair_rows[0][2]:.4f}" if pair_rows else "n/a"
    pair_count = int(summary.get("pair_count")) if isinstance(summary.get("pair_count"), (int, float)) else len(pair_rows)
    cards = [
        ("Lenses", len(lenses)),
        ("Lens Pairs", pair_count),
        ("Matrix", matrix_label),
        ("Strongest Pair", strongest_pair),
        ("Strongest Value", strongest_value),
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


def _matrix_figure(lenses: list[str], matrix: list[list[float | None]], matrix_label: str, matrix_key: str) -> go.Figure:
    if not lenses or not matrix:
        return _empty_figure(matrix_label)

    is_pairwise = matrix_key == "pairwise"
    if is_pairwise:
        zmin = 0
        zmax = max((value for row in matrix for value in row if isinstance(value, (int, float))), default=1.0)
        colorscale = "Viridis"
        zmid = None
    else:
        finite_values = [value for row in matrix for value in row if isinstance(value, (int, float))]
        limit = max((abs(value) for value in finite_values), default=1.0)
        zmin = -limit
        zmax = limit
        colorscale = "RdBu"
        zmid = 0.0

    figure = go.Figure(
        data=[
            go.Heatmap(
                z=matrix,
                x=lenses,
                y=lenses,
                colorscale=colorscale,
                zmin=zmin,
                zmax=zmax,
                zmid=zmid,
                colorbar={"title": "Value"},
                hovertemplate="Lens A: %{y}<br>Lens B: %{x}<br>Value: %{z:.4f}<extra></extra>",
            )
        ]
    )
    figure.update_layout(title=matrix_label, template="plotly_white", xaxis_title="Lens", yaxis_title="Lens")
    return figure


def _pair_figure(pair_rows: list[tuple[str, str, float]], matrix_label: str, matrix_key: str, top_n: int) -> go.Figure:
    if not pair_rows:
        return _empty_figure("Top Lens Pairs")
    top_rows = pair_rows[:top_n]
    x_values = [f"{left} / {right}" for left, right, _ in top_rows]
    y_values = [value for _, _, value in top_rows]
    if matrix_key == "pairwise":
        colors = "#fd7e14"
    else:
        colors = ["#198754" if value >= 0 else "#dc3545" for value in y_values]

    figure = go.Figure(data=[go.Bar(x=x_values, y=y_values, marker_color=colors)])
    figure.update_layout(title=f"Top Lens Pairs by {matrix_label}", template="plotly_white", xaxis_title="Lens Pair")
    return figure


def _pair_table(pair_rows: list[tuple[str, str, float]], matrix_label: str, top_n: int):
    if not pair_rows:
        return dbc.Alert("No lens pair matrix values are available.", color="warning", className="mb-0")
    table_rows = [
        html.Tr([html.Td(left), html.Td(right), html.Td(f"{value:.4f}")])
        for left, right, value in pair_rows[:top_n]
    ]
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(f"Top Lens Pairs ({matrix_label})", className="card-title"),
                dbc.Table(
                    [
                        html.Thead(html.Tr([html.Th("Lens A"), html.Th("Lens B"), html.Th("Value")])),
                        html.Tbody(table_rows),
                    ],
                    bordered=True,
                    striped=True,
                    hover=True,
                    responsive=True,
                    size="sm",
                    class_name="mb-0",
                ),
            ]
        ),
        className="shadow-sm",
    )


layout = dbc.Container(
    [
        dcc.Interval(id="news-lens-corr-load", interval=50, n_intervals=0, max_intervals=1),
        dbc.Row([dbc.Col(html.H3("News Lens Correlations", className="mb-2"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    html.P(
                        "This page compares lens correlation and covariance matrices. It uses precomputed "
                        "backend-derived matrices with fallback to upstream analysis matrices for compatibility.",
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
                            id="news-lens-corr-mode",
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
                        dcc.Input(id="news-lens-corr-snapshot-date", type="date", className="form-control", disabled=True),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Matrix"),
                        dcc.Dropdown(
                            id="news-lens-corr-matrix",
                            options=MATRIX_OPTIONS,
                            value="corr_raw",
                            clearable=False,
                        ),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        dbc.Label("Top pairs"),
                        dcc.Slider(
                            id="news-lens-corr-top-n",
                            min=5,
                            max=30,
                            step=1,
                            value=10,
                            marks={5: "5", 10: "10", 20: "20", 30: "30"},
                        ),
                    ],
                    md=3,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-lens-corr-refresh", color="secondary"),
                    ],
                    md=2,
                ),
            ],
            className="mb-3",
        ),
        dbc.Row([dbc.Col(html.Div(id="news-lens-corr-status"), width=12)]),
        dbc.Row(id="news-lens-corr-cards"),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-lens-corr-heatmap"), lg=8, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-lens-corr-pairs"), lg=4, className="mb-3"),
            ]
        ),
        dbc.Row([dbc.Col(html.Div(id="news-lens-corr-table"), width=12)]),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-lens-corr-status", "children"),
    Output("news-lens-corr-cards", "children"),
    Output("news-lens-corr-heatmap", "figure"),
    Output("news-lens-corr-pairs", "figure"),
    Output("news-lens-corr-table", "children"),
    Input("news-lens-corr-load", "n_intervals"),
    Input("news-lens-corr-refresh", "n_clicks"),
    Input("news-lens-corr-matrix", "value"),
    Input("news-lens-corr-top-n", "value"),
    State("news-lens-corr-mode", "value"),
    State("news-lens-corr-snapshot-date", "value"),
)
def load_news_lens_correlations(_load_tick, _refresh_clicks, matrix_key, top_n, data_mode, snapshot_date):
    force_refresh = ctx.triggered_id == "news-lens-corr-refresh"
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
        return alert, _summary_cards([], [], "No data"), empty, empty, alert

    meta = payload.get("meta", {})
    data = payload.get("data", {})
    lens_correlations, corr_source = _select_lens_correlations(data if isinstance(data, dict) else {})
    matrix_name = matrix_key if isinstance(matrix_key, str) else "corr_raw"
    pair_limit = int(top_n) if isinstance(top_n, (int, float)) else 10
    pair_limit = max(1, min(pair_limit, 30))

    lenses, matrix, matrix_label = _matrix_payload(lens_correlations, matrix_name)
    backend_pair_rows = _pair_rows_from_backend(lens_correlations, matrix_name)
    pair_rows = backend_pair_rows if backend_pair_rows is not None else _pair_rows(lenses, matrix, matrix_name)
    matrix_summary = _matrix_summary_from_backend(lens_correlations, matrix_name)

    return (
        build_status_alert(
            meta,
            leading_parts=[f"Source: {corr_source}", f"Matrix: {matrix_label}", f"Lenses: {len(lenses)}"],
        ),
        _summary_cards(lenses, pair_rows, matrix_label, matrix_summary),
        _matrix_figure(lenses, matrix, matrix_label, matrix_name),
        _pair_figure(pair_rows, matrix_label, matrix_name, pair_limit),
        _pair_table(pair_rows, matrix_label, pair_limit),
    )


@callback(
    Output("news-lens-corr-snapshot-date", "disabled"),
    Input("news-lens-corr-mode", "value"),
)
def toggle_lens_correlation_snapshot_input(data_mode):
    return data_mode != "snapshot"
