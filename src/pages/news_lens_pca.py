from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, ctx, dcc, html

from src.pages.news_page_utils import api_get, build_status_alert, snapshot_param


dash.register_page(
    __name__,
    path="/news/lens-pca",
    name="News Lens PCA",
    title="NewsLens | News Lens PCA",
)


def _select_lens_pca(data: dict) -> tuple[dict, str]:
    if not isinstance(data, dict):
        return {}, "missing"
    derived = data.get("derived")
    derived_pca = derived.get("lens_pca") if isinstance(derived, dict) else None
    if isinstance(derived_pca, dict):
        return derived_pca, "derived"
    return {}, "missing"


def _select_lens_mds(data: dict) -> tuple[dict, str]:
    if not isinstance(data, dict):
        return {}, "missing"
    derived = data.get("derived")
    derived_mds = derived.get("lens_mds") if isinstance(derived, dict) else None
    if isinstance(derived_mds, dict):
        return derived_mds, "derived"
    return {}, "missing"


def _select_lens_separation(data: dict) -> tuple[dict, str]:
    if not isinstance(data, dict):
        return {}, "missing"
    derived = data.get("derived")
    derived_sep = derived.get("lens_separation") if isinstance(derived, dict) else None
    if isinstance(derived_sep, dict):
        return derived_sep, "derived"
    return {}, "missing"


def _select_lens_time_series(data: dict) -> tuple[dict, str]:
    if not isinstance(data, dict):
        return {}, "missing"
    derived = data.get("derived")
    derived_time = derived.get("lens_time_series") if isinstance(derived, dict) else None
    if isinstance(derived_time, dict):
        return derived_time, "derived"
    return {}, "missing"


def _select_lens_temporal_embedding(data: dict) -> tuple[dict, str]:
    if not isinstance(data, dict):
        return {}, "missing"
    derived = data.get("derived")
    derived_embedding = derived.get("lens_temporal_embedding") if isinstance(derived, dict) else None
    if isinstance(derived_embedding, dict):
        return derived_embedding, "derived"
    return {}, "missing"


def _select_lens_temporal_embedding_mds(data: dict) -> tuple[dict, str]:
    if not isinstance(data, dict):
        return {}, "missing"
    derived = data.get("derived")
    derived_embedding = derived.get("lens_temporal_embedding_mds") if isinstance(derived, dict) else None
    if isinstance(derived_embedding, dict):
        return derived_embedding, "derived"
    return {}, "missing"


def _temporal_slider_config(
    temporal_payload: dict,
    temporal_mds_payload: dict,
    requested_value: int | None,
    is_playing: bool,
    play_tick: int | None,
    step_size: int = 1,
) -> tuple[int, dict[int, str], int, int]:
    day_to_date: dict[int, str] = {}
    all_day_indexes: list[int] = []
    for payload in (temporal_payload, temporal_mds_payload):
        centroids = payload.get("day_centroids") if isinstance(payload, dict) and isinstance(payload.get("day_centroids"), list) else []
        for row in centroids:
            if not isinstance(row, dict):
                continue
            day_idx = row.get("day_index")
            day_str = row.get("date")
            if not isinstance(day_idx, (int, float)):
                continue
            day_int = int(day_idx)
            all_day_indexes.append(day_int)
            if isinstance(day_str, str) and day_str.strip():
                day_to_date.setdefault(day_int, day_str.strip())

    if not all_day_indexes:
        return 0, {0: "All"}, 0, 1

    max_day = max(all_day_indexes)
    min_day = min(all_day_indexes)
    if min_day < 0:
        min_day = 0
    step = max(1, int(step_size))

    if is_playing:
        tick = int(play_tick) if isinstance(play_tick, (int, float)) else 0
        day_value = min_day + ((tick * step) % (max_day - min_day + 1))
    else:
        if isinstance(requested_value, (int, float)):
            day_value = int(requested_value)
        else:
            day_value = max_day
        day_value = max(min_day, min(max_day, day_value))

    if max_day <= min_day:
        label = day_to_date.get(max_day, "All")
        return max_day, {max_day: label}, day_value, 1

    mid_day = min_day + (max_day - min_day) // 2
    marks = {
        min_day: day_to_date.get(min_day, str(min_day)),
        mid_day: day_to_date.get(mid_day, str(mid_day)),
        max_day: day_to_date.get(max_day, str(max_day)),
    }
    slider_step = step if step > 1 else 1
    return max_day, marks, day_value, slider_step


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        title=title,
        template="plotly_white",
        margin={"l": 30, "r": 20, "t": 60, "b": 40},
    )
    return figure


def _summary_cards(pca_payload: dict) -> list:
    status = str(pca_payload.get("status") or "missing")
    n_articles = pca_payload.get("n_articles")
    n_lenses = pca_payload.get("n_lenses")
    explained = pca_payload.get("explained_variance") if isinstance(pca_payload.get("explained_variance"), list) else []
    pc1 = explained[0] if explained else {}
    pc2 = explained[1] if len(explained) > 1 else {}

    pc1_ratio = pc1.get("explained_variance_ratio")
    pc1_cum = pc1.get("cumulative_variance_ratio")
    pc2_cum = pc2.get("cumulative_variance_ratio")
    cumulative_two = pc2_cum if isinstance(pc2_cum, (int, float)) else pc1_cum

    top_driver = "n/a"
    drivers = pca_payload.get("variance_drivers")
    if isinstance(drivers, list) and drivers:
        first = drivers[0]
        if isinstance(first, dict) and isinstance(first.get("lens"), str):
            top_driver = first["lens"]

    cards = [
        ("Status", status),
        ("Complete Articles", n_articles if isinstance(n_articles, (int, float)) else "n/a"),
        ("Lenses", n_lenses if isinstance(n_lenses, (int, float)) else "n/a"),
        ("PC1 Variance", f"{float(pc1_ratio) * 100:.1f}%" if isinstance(pc1_ratio, (int, float)) else "n/a"),
        ("PC1-2 Cumulative", f"{float(cumulative_two) * 100:.1f}%" if isinstance(cumulative_two, (int, float)) else "n/a"),
        ("Top Variance Driver", top_driver),
    ]
    return [
        dbc.Col(
            dbc.Card(
                dbc.CardBody([html.P(label, className="text-muted mb-1"), html.H4(str(value), className="mb-0")]),
                className="shadow-sm",
            ),
            md=6,
            lg=2,
            className="mb-3",
        )
        for label, value in cards
    ]


def _explained_variance_figure(pca_payload: dict) -> go.Figure:
    rows = pca_payload.get("explained_variance") if isinstance(pca_payload.get("explained_variance"), list) else []
    cleaned_rows = [row for row in rows if isinstance(row, dict) and isinstance(row.get("component"), str)]
    if not cleaned_rows:
        return _empty_figure("Explained Variance by Principal Component")

    components = [str(row.get("component")) for row in cleaned_rows]
    explained = [
        float(row.get("explained_variance_ratio")) * 100.0
        if isinstance(row.get("explained_variance_ratio"), (int, float))
        else 0.0
        for row in cleaned_rows
    ]
    cumulative = [
        float(row.get("cumulative_variance_ratio")) * 100.0
        if isinstance(row.get("cumulative_variance_ratio"), (int, float))
        else 0.0
        for row in cleaned_rows
    ]

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=components,
            y=explained,
            name="Explained Variance %",
            marker_color="#0d6efd",
            hovertemplate="Component: %{x}<br>Explained: %{y:.2f}%<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=components,
            y=cumulative,
            mode="lines+markers",
            name="Cumulative Variance %",
            marker_color="#198754",
            yaxis="y2",
            hovertemplate="Component: %{x}<br>Cumulative: %{y:.2f}%<extra></extra>",
        )
    )
    figure.update_layout(
        title="Explained Variance by Principal Component",
        template="plotly_white",
        xaxis_title="Principal Component",
        yaxis={"title": "Explained Variance %", "rangemode": "tozero"},
        yaxis2={"title": "Cumulative %", "overlaying": "y", "side": "right", "rangemode": "tozero"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1.0},
    )
    return figure


def _article_scatter_figure(pca_payload: dict, color_by: str, max_points: int) -> go.Figure:
    points = pca_payload.get("article_points") if isinstance(pca_payload.get("article_points"), list) else []
    usable = [
        row
        for row in points
        if isinstance(row, dict) and isinstance(row.get("pc1"), (int, float)) and isinstance(row.get("pc2"), (int, float))
    ]
    if not usable:
        return _empty_figure("Article Distribution in PC1/PC2 Space")

    limit = int(max_points) if isinstance(max_points, (int, float)) else 300
    limit = max(limit, 50)
    ranked = sorted(
        usable,
        key=lambda row: (abs(float(row.get("pc1") or 0.0)) + abs(float(row.get("pc2") or 0.0))),
        reverse=True,
    )[:limit]

    grouped: dict[str, list[dict]] = {}
    for row in ranked:
        if color_by == "strongest_lens":
            key = str(row.get("strongest_lens") or "Unknown")
        else:
            key = str(row.get("source") or "Unknown")
        grouped.setdefault(key, []).append(row)

    figure = go.Figure()
    for label, rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0].lower())):
        figure.add_trace(
            go.Scatter(
                x=[float(row["pc1"]) for row in rows],
                y=[float(row["pc2"]) for row in rows],
                mode="markers",
                name=label,
                text=[str(row.get("title") or "Untitled") for row in rows],
                customdata=[
                    [
                        row.get("source"),
                        row.get("strongest_lens"),
                        row.get("published_at"),
                    ]
                    for row in rows
                ],
                hovertemplate=(
                    "Title: %{text}<br>"
                    "PC1: %{x:.3f}<br>"
                    "PC2: %{y:.3f}<br>"
                    "Source: %{customdata[0]}<br>"
                    "Strongest Lens: %{customdata[1]}<br>"
                    "Published: %{customdata[2]}<extra></extra>"
                ),
                marker={"size": 8, "opacity": 0.75},
            )
        )

    centroids = pca_payload.get("source_centroids") if isinstance(pca_payload.get("source_centroids"), list) else []
    if color_by == "source":
        centroid_rows = [
            row
            for row in centroids
            if isinstance(row, dict) and isinstance(row.get("pc1"), (int, float)) and isinstance(row.get("pc2"), (int, float))
        ]
        if centroid_rows:
            figure.add_trace(
                go.Scatter(
                    x=[float(row["pc1"]) for row in centroid_rows],
                    y=[float(row["pc2"]) for row in centroid_rows],
                    mode="markers+text",
                    name="Source Centroids",
                    text=[str(row.get("source")) for row in centroid_rows],
                    textposition="top center",
                    marker={"symbol": "x", "size": 12, "color": "#111111"},
                    hovertemplate="Source: %{text}<br>PC1: %{x:.3f}<br>PC2: %{y:.3f}<extra></extra>",
                )
            )

    figure.update_layout(
        title="Article Distribution in PC1/PC2 Space",
        template="plotly_white",
        xaxis_title="PC1",
        yaxis_title="PC2",
        legend={"orientation": "v"},
    )
    return figure


def _lens_time_series_figure(time_series_payload: dict, top_n: int = 8) -> go.Figure:
    if not isinstance(time_series_payload, dict) or str(time_series_payload.get("status") or "") != "ok":
        return _empty_figure("Lens Time Series (Daily Means)")

    series = time_series_payload.get("series") if isinstance(time_series_payload.get("series"), list) else []
    rows = [row for row in series if isinstance(row, dict) and isinstance(row.get("lens"), str)]
    if not rows:
        return _empty_figure("Lens Time Series (Daily Means)")

    ranked = sorted(
        rows,
        key=lambda row: max(
            (float(point.get("count") or 0.0) for point in (row.get("points") or []) if isinstance(point, dict)),
            default=0.0,
        ),
        reverse=True,
    )[: max(3, int(top_n))]

    figure = go.Figure()
    for row in ranked:
        lens_name = str(row.get("lens"))
        points = row.get("points") if isinstance(row.get("points"), list) else []
        usable = [
            point
            for point in points
            if isinstance(point, dict) and isinstance(point.get("date"), str) and isinstance(point.get("mean"), (int, float))
        ]
        if not usable:
            continue
        figure.add_trace(
            go.Scatter(
                x=[str(point["date"]) for point in usable],
                y=[float(point["mean"]) for point in usable],
                mode="lines+markers",
                name=lens_name,
                customdata=[[point.get("count"), point.get("median"), point.get("min"), point.get("max")] for point in usable],
                hovertemplate=(
                    "Lens: "
                    + lens_name
                    + "<br>Date: %{x}<br>Mean: %{y:.2f}<br>N: %{customdata[0]}<br>"
                    + "Median: %{customdata[1]:.2f}<br>Min/Max: %{customdata[2]:.2f} / %{customdata[3]:.2f}<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        title="Lens Time Series (Daily Mean Percent)",
        template="plotly_white",
        xaxis_title="Date (UTC)",
        yaxis_title="Lens Percent",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0.0},
    )
    return figure


def _temporal_embedding_figure(
    temporal_payload: dict,
    max_day_index: int | None = None,
    trailing_window_days: int | None = None,
    step_size: int = 1,
) -> go.Figure:
    if not isinstance(temporal_payload, dict) or str(temporal_payload.get("status") or "") != "ok":
        return _empty_figure("Temporal Trajectory in PC1/PC2")

    points = temporal_payload.get("points") if isinstance(temporal_payload.get("points"), list) else []
    usable = [
        row
        for row in points
        if isinstance(row, dict)
        and isinstance(row.get("pc1"), (int, float))
        and isinstance(row.get("pc2"), (int, float))
        and isinstance(row.get("day_index"), (int, float))
    ]
    if isinstance(max_day_index, int):
        usable = [row for row in usable if int(row.get("day_index", 0)) <= max_day_index]
    if isinstance(max_day_index, int) and isinstance(trailing_window_days, int) and trailing_window_days > 0:
        min_day_index = max_day_index - trailing_window_days + 1
        usable = [row for row in usable if int(row.get("day_index", 0)) >= min_day_index]
    step = max(1, int(step_size))
    if step > 1 and isinstance(max_day_index, int):
        usable = [
            row
            for row in usable
            if (int(row.get("day_index", 0)) % step == 0) or (int(row.get("day_index", 0)) == max_day_index)
        ]
    if not usable:
        return _empty_figure("Temporal Trajectory in PC1/PC2")

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[float(row["pc1"]) for row in usable],
            y=[float(row["pc2"]) for row in usable],
            mode="markers",
            name="Articles",
            text=[str(row.get("title") or "Untitled") for row in usable],
            customdata=[[row.get("source"), row.get("date"), row.get("strongest_lens")] for row in usable],
            marker={
                "size": 8,
                "opacity": 0.7,
                "color": [float(row["day_index"]) for row in usable],
                "colorscale": "Viridis",
                "showscale": True,
                "colorbar": {"title": "Day Index"},
            },
            hovertemplate=(
                "Title: %{text}<br>PC1: %{x:.3f}<br>PC2: %{y:.3f}<br>"
                "Source: %{customdata[0]}<br>Date: %{customdata[1]}<br>"
                "Strongest Lens: %{customdata[2]}<extra></extra>"
            ),
        )
    )

    centroids = temporal_payload.get("day_centroids") if isinstance(temporal_payload.get("day_centroids"), list) else []
    centroid_rows = [
        row
        for row in centroids
        if isinstance(row, dict) and isinstance(row.get("pc1"), (int, float)) and isinstance(row.get("pc2"), (int, float))
    ]
    if isinstance(max_day_index, int):
        centroid_rows = [row for row in centroid_rows if int(row.get("day_index", 0)) <= max_day_index]
    if isinstance(max_day_index, int) and isinstance(trailing_window_days, int) and trailing_window_days > 0:
        min_day_index = max_day_index - trailing_window_days + 1
        centroid_rows = [row for row in centroid_rows if int(row.get("day_index", 0)) >= min_day_index]
    if step > 1 and isinstance(max_day_index, int):
        centroid_rows = [
            row
            for row in centroid_rows
            if (int(row.get("day_index", 0)) % step == 0) or (int(row.get("day_index", 0)) == max_day_index)
        ]
    if centroid_rows:
        figure.add_trace(
            go.Scatter(
                x=[float(row["pc1"]) for row in centroid_rows],
                y=[float(row["pc2"]) for row in centroid_rows],
                mode="lines+markers",
                name="Daily Centroid Path",
                text=[str(row.get("date") or "") for row in centroid_rows],
                marker={"size": 9, "symbol": "diamond", "color": "#111111"},
                line={"width": 2, "color": "#111111"},
                hovertemplate="Date: %{text}<br>PC1: %{x:.3f}<br>PC2: %{y:.3f}<extra></extra>",
            )
        )

    figure.update_layout(
        title="Temporal Trajectory in PC1/PC2",
        template="plotly_white",
        xaxis_title="PC1",
        yaxis_title="PC2",
    )
    return figure


def _temporal_embedding_mds_figure(
    temporal_payload: dict,
    max_day_index: int | None = None,
    trailing_window_days: int | None = None,
    step_size: int = 1,
) -> go.Figure:
    if not isinstance(temporal_payload, dict) or str(temporal_payload.get("status") or "") != "ok":
        return _empty_figure("Temporal Trajectory in MDS1/MDS2")

    points = temporal_payload.get("points") if isinstance(temporal_payload.get("points"), list) else []
    usable = [
        row
        for row in points
        if isinstance(row, dict)
        and isinstance(row.get("mds1"), (int, float))
        and isinstance(row.get("mds2"), (int, float))
        and isinstance(row.get("day_index"), (int, float))
    ]
    if isinstance(max_day_index, int):
        usable = [row for row in usable if int(row.get("day_index", 0)) <= max_day_index]
    if isinstance(max_day_index, int) and isinstance(trailing_window_days, int) and trailing_window_days > 0:
        min_day_index = max_day_index - trailing_window_days + 1
        usable = [row for row in usable if int(row.get("day_index", 0)) >= min_day_index]
    step = max(1, int(step_size))
    if step > 1 and isinstance(max_day_index, int):
        usable = [
            row
            for row in usable
            if (int(row.get("day_index", 0)) % step == 0) or (int(row.get("day_index", 0)) == max_day_index)
        ]
    if not usable:
        return _empty_figure("Temporal Trajectory in MDS1/MDS2")

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[float(row["mds1"]) for row in usable],
            y=[float(row["mds2"]) for row in usable],
            mode="markers",
            name="Articles",
            text=[str(row.get("title") or "Untitled") for row in usable],
            customdata=[[row.get("source"), row.get("date"), row.get("strongest_lens")] for row in usable],
            marker={
                "size": 8,
                "opacity": 0.7,
                "color": [float(row["day_index"]) for row in usable],
                "colorscale": "Plasma",
                "showscale": True,
                "colorbar": {"title": "Day Index"},
            },
            hovertemplate=(
                "Title: %{text}<br>MDS1: %{x:.3f}<br>MDS2: %{y:.3f}<br>"
                "Source: %{customdata[0]}<br>Date: %{customdata[1]}<br>"
                "Strongest Lens: %{customdata[2]}<extra></extra>"
            ),
        )
    )

    centroids = temporal_payload.get("day_centroids") if isinstance(temporal_payload.get("day_centroids"), list) else []
    centroid_rows = [
        row
        for row in centroids
        if isinstance(row, dict) and isinstance(row.get("mds1"), (int, float)) and isinstance(row.get("mds2"), (int, float))
    ]
    if isinstance(max_day_index, int):
        centroid_rows = [row for row in centroid_rows if int(row.get("day_index", 0)) <= max_day_index]
    if isinstance(max_day_index, int) and isinstance(trailing_window_days, int) and trailing_window_days > 0:
        min_day_index = max_day_index - trailing_window_days + 1
        centroid_rows = [row for row in centroid_rows if int(row.get("day_index", 0)) >= min_day_index]
    if step > 1 and isinstance(max_day_index, int):
        centroid_rows = [
            row
            for row in centroid_rows
            if (int(row.get("day_index", 0)) % step == 0) or (int(row.get("day_index", 0)) == max_day_index)
        ]
    if centroid_rows:
        figure.add_trace(
            go.Scatter(
                x=[float(row["mds1"]) for row in centroid_rows],
                y=[float(row["mds2"]) for row in centroid_rows],
                mode="lines+markers",
                name="Daily Centroid Path",
                text=[str(row.get("date") or "") for row in centroid_rows],
                marker={"size": 9, "symbol": "diamond", "color": "#111111"},
                line={"width": 2, "color": "#111111"},
                hovertemplate="Date: %{text}<br>MDS1: %{x:.3f}<br>MDS2: %{y:.3f}<extra></extra>",
            )
        )

    figure.update_layout(
        title="Temporal Trajectory in MDS1/MDS2",
        template="plotly_white",
        xaxis_title="MDS1",
        yaxis_title="MDS2",
    )
    return figure


def _temporal_diagnostics_figure(
    temporal_payload: dict,
    temporal_mds_payload: dict,
    max_day_index: int | None = None,
    trailing_window_days: int | None = None,
    step_size: int = 1,
) -> go.Figure:
    if not isinstance(temporal_payload, dict) or str(temporal_payload.get("status") or "") != "ok":
        return _empty_figure("Temporal Diagnostics: Volume and Drift")

    centroid_rows = temporal_payload.get("day_centroids") if isinstance(temporal_payload.get("day_centroids"), list) else []
    centroid_rows = [
        row
        for row in centroid_rows
        if isinstance(row, dict)
        and isinstance(row.get("pc1"), (int, float))
        and isinstance(row.get("pc2"), (int, float))
        and isinstance(row.get("day_index"), (int, float))
        and isinstance(row.get("date"), str)
    ]
    if isinstance(max_day_index, int):
        centroid_rows = [row for row in centroid_rows if int(row.get("day_index", 0)) <= max_day_index]
    if isinstance(max_day_index, int) and isinstance(trailing_window_days, int) and trailing_window_days > 0:
        min_day_index = max_day_index - trailing_window_days + 1
        centroid_rows = [row for row in centroid_rows if int(row.get("day_index", 0)) >= min_day_index]
    step = max(1, int(step_size))
    if step > 1 and isinstance(max_day_index, int):
        centroid_rows = [
            row
            for row in centroid_rows
            if (int(row.get("day_index", 0)) % step == 0) or (int(row.get("day_index", 0)) == max_day_index)
        ]
    if not centroid_rows:
        return _empty_figure("Temporal Diagnostics: Volume and Drift")

    centroid_rows = sorted(centroid_rows, key=lambda row: int(row.get("day_index", 0)))
    pca_drift: list[float] = []
    for idx, row in enumerate(centroid_rows):
        if idx == 0:
            pca_drift.append(0.0)
            continue
        prev = centroid_rows[idx - 1]
        dx = float(row.get("pc1", 0.0)) - float(prev.get("pc1", 0.0))
        dy = float(row.get("pc2", 0.0)) - float(prev.get("pc2", 0.0))
        pca_drift.append((dx * dx + dy * dy) ** 0.5)

    mds_by_day: dict[int, tuple[float, float]] = {}
    if isinstance(temporal_mds_payload, dict) and str(temporal_mds_payload.get("status") or "") == "ok":
        mds_centroids = (
            temporal_mds_payload.get("day_centroids") if isinstance(temporal_mds_payload.get("day_centroids"), list) else []
        )
        for row in mds_centroids:
            if (
                isinstance(row, dict)
                and isinstance(row.get("day_index"), (int, float))
                and isinstance(row.get("mds1"), (int, float))
                and isinstance(row.get("mds2"), (int, float))
            ):
                mds_by_day[int(row["day_index"])] = (float(row["mds1"]), float(row["mds2"]))

    mds_drift: list[float | None] = []
    for idx, row in enumerate(centroid_rows):
        day_idx = int(row.get("day_index", 0))
        current = mds_by_day.get(day_idx)
        if idx == 0 or not current:
            mds_drift.append(0.0 if idx == 0 else None)
            continue
        prev_day = int(centroid_rows[idx - 1].get("day_index", 0))
        prev = mds_by_day.get(prev_day)
        if not prev:
            mds_drift.append(None)
            continue
        dx = current[0] - prev[0]
        dy = current[1] - prev[1]
        mds_drift.append((dx * dx + dy * dy) ** 0.5)

    points = temporal_payload.get("points") if isinstance(temporal_payload.get("points"), list) else []
    points = [
        row
        for row in points
        if isinstance(row, dict) and isinstance(row.get("day_index"), (int, float)) and isinstance(row.get("date"), str)
    ]
    if isinstance(max_day_index, int):
        points = [row for row in points if int(row.get("day_index", 0)) <= max_day_index]
    if isinstance(max_day_index, int) and isinstance(trailing_window_days, int) and trailing_window_days > 0:
        min_day_index = max_day_index - trailing_window_days + 1
        points = [row for row in points if int(row.get("day_index", 0)) >= min_day_index]
    if step > 1 and isinstance(max_day_index, int):
        points = [
            row
            for row in points
            if (int(row.get("day_index", 0)) % step == 0) or (int(row.get("day_index", 0)) == max_day_index)
        ]

    volume_by_day: dict[int, int] = {}
    for row in points:
        day_idx = int(row.get("day_index", 0))
        volume_by_day[day_idx] = volume_by_day.get(day_idx, 0) + 1

    dates = [str(row["date"]) for row in centroid_rows]
    day_indexes = [int(row.get("day_index", 0)) for row in centroid_rows]
    volumes = [int(volume_by_day.get(day_idx, 0)) for day_idx in day_indexes]

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=dates,
            y=volumes,
            name="Article Count",
            marker_color="#6c757d",
            opacity=0.5,
            hovertemplate="Date: %{x}<br>Articles: %{y}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=dates,
            y=pca_drift,
            mode="lines+markers",
            name="PCA Centroid Drift",
            marker={"size": 7},
            line={"width": 2, "color": "#0d6efd"},
            yaxis="y2",
            hovertemplate="Date: %{x}<br>PCA drift: %{y:.4f}<extra></extra>",
        )
    )
    if any(value is not None for value in mds_drift):
        figure.add_trace(
            go.Scatter(
                x=dates,
                y=mds_drift,
                mode="lines+markers",
                name="MDS Centroid Drift",
                marker={"size": 7},
                line={"width": 2, "color": "#198754", "dash": "dot"},
                yaxis="y2",
                hovertemplate="Date: %{x}<br>MDS drift: %{y:.4f}<extra></extra>",
            )
        )

    figure.update_layout(
        title="Temporal Diagnostics: Volume and Drift",
        template="plotly_white",
        xaxis_title="Date (UTC)",
        yaxis={"title": "Article Count", "rangemode": "tozero"},
        yaxis2={"title": "Centroid Drift", "overlaying": "y", "side": "right", "rangemode": "tozero"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0.0},
    )
    return figure


def _mds_scatter_figure(mds_payload: dict, color_by: str, max_points: int) -> go.Figure:
    points = mds_payload.get("article_points") if isinstance(mds_payload.get("article_points"), list) else []
    usable = [
        row
        for row in points
        if isinstance(row, dict) and isinstance(row.get("mds1"), (int, float)) and isinstance(row.get("mds2"), (int, float))
    ]
    if not usable:
        return _empty_figure("Article Distribution in MDS1/MDS2 Space")

    limit = int(max_points) if isinstance(max_points, (int, float)) else 300
    limit = max(limit, 50)
    ranked = sorted(
        usable,
        key=lambda row: (abs(float(row.get("mds1") or 0.0)) + abs(float(row.get("mds2") or 0.0))),
        reverse=True,
    )[:limit]

    grouped: dict[str, list[dict]] = {}
    for row in ranked:
        if color_by == "strongest_lens":
            key = str(row.get("strongest_lens") or "Unknown")
        else:
            key = str(row.get("source") or "Unknown")
        grouped.setdefault(key, []).append(row)

    figure = go.Figure()
    for label, rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0].lower())):
        figure.add_trace(
            go.Scatter(
                x=[float(row["mds1"]) for row in rows],
                y=[float(row["mds2"]) for row in rows],
                mode="markers",
                name=label,
                text=[str(row.get("title") or "Untitled") for row in rows],
                customdata=[
                    [
                        row.get("source"),
                        row.get("strongest_lens"),
                    ]
                    for row in rows
                ],
                hovertemplate=(
                    "Title: %{text}<br>"
                    "MDS1: %{x:.3f}<br>"
                    "MDS2: %{y:.3f}<br>"
                    "Source: %{customdata[0]}<br>"
                    "Strongest Lens: %{customdata[1]}<extra></extra>"
                ),
                marker={"size": 8, "opacity": 0.75},
            )
        )

    centroids = mds_payload.get("source_centroids") if isinstance(mds_payload.get("source_centroids"), list) else []
    if color_by == "source":
        centroid_rows = [
            row
            for row in centroids
            if isinstance(row, dict) and isinstance(row.get("mds1"), (int, float)) and isinstance(row.get("mds2"), (int, float))
        ]
        if centroid_rows:
            figure.add_trace(
                go.Scatter(
                    x=[float(row["mds1"]) for row in centroid_rows],
                    y=[float(row["mds2"]) for row in centroid_rows],
                    mode="markers+text",
                    name="Source Centroids",
                    text=[str(row.get("source")) for row in centroid_rows],
                    textposition="top center",
                    marker={"symbol": "x", "size": 12, "color": "#111111"},
                    hovertemplate="Source: %{text}<br>MDS1: %{x:.3f}<br>MDS2: %{y:.3f}<extra></extra>",
                )
            )

    stress = mds_payload.get("stress")
    stress_text = f" (Stress: {float(stress):.3f})" if isinstance(stress, (int, float)) else ""
    figure.update_layout(
        title=f"Article Distribution in MDS1/MDS2 Space{stress_text}",
        template="plotly_white",
        xaxis_title="MDS1",
        yaxis_title="MDS2",
        legend={"orientation": "v"},
    )
    return figure


def _loadings_heatmap_figure(pca_payload: dict) -> go.Figure:
    loadings = pca_payload.get("loadings") if isinstance(pca_payload.get("loadings"), dict) else {}
    components = loadings.get("components") if isinstance(loadings.get("components"), list) else []
    lenses = loadings.get("lenses") if isinstance(loadings.get("lenses"), list) else []
    matrix = loadings.get("matrix") if isinstance(loadings.get("matrix"), list) else []
    if not components or not lenses or not matrix:
        return _empty_figure("PCA Component Loadings")

    normalized_matrix: list[list[float]] = []
    for row in matrix[: len(components)]:
        if not isinstance(row, list):
            continue
        normalized_row = []
        for value in row[: len(lenses)]:
            normalized_row.append(float(value) if isinstance(value, (int, float)) else 0.0)
        if len(normalized_row) < len(lenses):
            normalized_row.extend([0.0] * (len(lenses) - len(normalized_row)))
        normalized_matrix.append(normalized_row)
    if not normalized_matrix:
        return _empty_figure("PCA Component Loadings")

    max_abs = max((abs(value) for row in normalized_matrix for value in row), default=1.0)
    if max_abs <= 0:
        max_abs = 1.0

    figure = go.Figure(
        data=[
            go.Heatmap(
                z=normalized_matrix,
                x=lenses,
                y=components,
                zmin=-max_abs,
                zmax=max_abs,
                zmid=0.0,
                colorscale="RdBu",
                colorbar={"title": "Loading"},
                hovertemplate="Component: %{y}<br>Lens: %{x}<br>Loading: %{z:.4f}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        title="PCA Component Loadings",
        template="plotly_white",
        xaxis_title="Lens",
        yaxis_title="Principal Component",
    )
    return figure


def _component_loading_figure(pca_payload: dict, component: str | None) -> go.Figure:
    loadings = pca_payload.get("loadings") if isinstance(pca_payload.get("loadings"), dict) else {}
    components = loadings.get("components") if isinstance(loadings.get("components"), list) else []
    lenses = loadings.get("lenses") if isinstance(loadings.get("lenses"), list) else []
    matrix = loadings.get("matrix") if isinstance(loadings.get("matrix"), list) else []
    if not components or not lenses or not matrix:
        return _empty_figure("Selected Component Lens Loadings")

    if component not in components:
        component = str(components[0]) if components else None
    if not component:
        return _empty_figure("Selected Component Lens Loadings")

    component_index = components.index(component)
    if component_index >= len(matrix) or not isinstance(matrix[component_index], list):
        return _empty_figure("Selected Component Lens Loadings")

    pairs = []
    row_values = matrix[component_index]
    for lens_index, lens_name in enumerate(lenses):
        value = row_values[lens_index] if lens_index < len(row_values) else None
        if isinstance(value, (int, float)):
            pairs.append((str(lens_name), float(value)))
    if not pairs:
        return _empty_figure("Selected Component Lens Loadings")

    pairs = sorted(pairs, key=lambda item: abs(item[1]), reverse=True)
    labels = [item[0] for item in pairs]
    values = [item[1] for item in pairs]
    colors = ["#198754" if value >= 0 else "#dc3545" for value in values]

    figure = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=values,
                marker_color=colors,
                hovertemplate="Lens: %{x}<br>Loading: %{y:.4f}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        title=f"Lens Loadings for {component}",
        template="plotly_white",
        xaxis_title="Lens",
        yaxis_title="Loading",
    )
    return figure


def _variance_driver_figure(pca_payload: dict, top_n: int = 12) -> go.Figure:
    drivers = pca_payload.get("variance_drivers") if isinstance(pca_payload.get("variance_drivers"), list) else []
    rows = [
        row
        for row in drivers
        if isinstance(row, dict) and isinstance(row.get("lens"), str) and isinstance(row.get("weighted_contribution"), (int, float))
    ]
    if not rows:
        return _empty_figure("Variance Drivers by Lens")

    limit = max(3, min(int(top_n), 25))
    ranked = sorted(rows, key=lambda row: float(row.get("weighted_contribution") or 0.0), reverse=True)[:limit]
    total = sum(float(row.get("weighted_contribution") or 0.0) for row in ranked)
    labels = [str(row.get("lens")) for row in ranked]
    values = [
        (float(row.get("weighted_contribution") or 0.0) / total * 100.0) if total > 0 else 0.0
        for row in ranked
    ]

    figure = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=values,
                marker_color="#fd7e14",
                hovertemplate="Lens: %{x}<br>Weighted contribution: %{y:.2f}%<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        title="Variance Drivers by Lens",
        template="plotly_white",
        xaxis_title="Lens",
        yaxis_title="Contribution %",
    )
    return figure


def _component_table(pca_payload: dict):
    rows = pca_payload.get("component_summary") if isinstance(pca_payload.get("component_summary"), list) else []
    typed_rows = [row for row in rows if isinstance(row, dict)]
    if not typed_rows:
        return dbc.Alert("No PCA component interpretation rows are available.", color="warning", className="mb-0")

    table_rows = []
    for row in typed_rows:
        component = str(row.get("component") or "n/a")
        explained_ratio = row.get("explained_variance_ratio")
        strongest_loadings = row.get("strongest_loadings") if isinstance(row.get("strongest_loadings"), list) else []
        top_positive = row.get("top_positive") if isinstance(row.get("top_positive"), list) else []
        top_negative = row.get("top_negative") if isinstance(row.get("top_negative"), list) else []

        strongest_text = ", ".join(
            f"{entry.get('lens')} ({float(entry.get('loading')):+.3f})"
            for entry in strongest_loadings[:3]
            if isinstance(entry, dict) and isinstance(entry.get("lens"), str) and isinstance(entry.get("loading"), (int, float))
        ) or "n/a"
        positive_text = ", ".join(
            f"{entry.get('lens')} ({float(entry.get('loading')):+.3f})"
            for entry in top_positive[:3]
            if isinstance(entry, dict) and isinstance(entry.get("lens"), str) and isinstance(entry.get("loading"), (int, float))
        ) or "n/a"
        negative_text = ", ".join(
            f"{entry.get('lens')} ({float(entry.get('loading')):+.3f})"
            for entry in top_negative[:3]
            if isinstance(entry, dict) and isinstance(entry.get("lens"), str) and isinstance(entry.get("loading"), (int, float))
        ) or "n/a"

        table_rows.append(
            html.Tr(
                [
                    html.Td(component),
                    html.Td(f"{float(explained_ratio) * 100:.2f}%" if isinstance(explained_ratio, (int, float)) else "n/a"),
                    html.Td(strongest_text),
                    html.Td(positive_text),
                    html.Td(negative_text),
                ]
            )
        )

    return dbc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Component"),
                        html.Th("Explained %"),
                        html.Th("Strongest Loadings"),
                        html.Th("Top Positive"),
                        html.Th("Top Negative"),
                    ]
                )
            ),
            html.Tbody(table_rows),
        ],
        bordered=True,
        striped=True,
        hover=True,
        responsive=True,
        size="sm",
    )


def _separation_summary(separation_payload: dict):
    status = str(separation_payload.get("status") or "missing")
    reason = str(separation_payload.get("reason") or "").strip()
    if status != "ok":
        detail = f"Lens separation unavailable ({status})"
        if reason:
            detail = f"{detail}: {reason}"
        return dbc.Alert(detail, color="warning", className="mb-3")

    n_sources = separation_payload.get("n_sources")
    ratio = separation_payload.get("separation_ratio")
    silhouette = separation_payload.get("silhouette_like_mean")
    within = separation_payload.get("within_source_mean_distance")
    between = separation_payload.get("between_source_centroid_mean_distance")
    return dbc.Row(
        [
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.P("Sources", className="text-muted mb-1"),
                            html.H4(str(n_sources) if isinstance(n_sources, (int, float)) else "n/a", className="mb-0"),
                        ]
                    ),
                    className="shadow-sm",
                ),
                md=6,
                lg=2,
                className="mb-3",
            ),
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.P("Separation Ratio", className="text-muted mb-1"),
                            html.H4(f"{float(ratio):.2f}" if isinstance(ratio, (int, float)) else "n/a", className="mb-0"),
                        ]
                    ),
                    className="shadow-sm",
                ),
                md=6,
                lg=2,
                className="mb-3",
            ),
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.P("Silhouette-like Mean", className="text-muted mb-1"),
                            html.H4(
                                f"{float(silhouette):.3f}" if isinstance(silhouette, (int, float)) else "n/a",
                                className="mb-0",
                            ),
                        ]
                    ),
                    className="shadow-sm",
                ),
                md=6,
                lg=2,
                className="mb-3",
            ),
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.P("Within Mean Dist", className="text-muted mb-1"),
                            html.H4(
                                f"{float(within):.3f}" if isinstance(within, (int, float)) else "n/a",
                                className="mb-0",
                            ),
                        ]
                    ),
                    className="shadow-sm",
                ),
                md=6,
                lg=3,
                className="mb-3",
            ),
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.P("Between Centroid Mean Dist", className="text-muted mb-1"),
                            html.H4(
                                f"{float(between):.3f}" if isinstance(between, (int, float)) else "n/a",
                                className="mb-0",
                            ),
                        ]
                    ),
                    className="shadow-sm",
                ),
                md=6,
                lg=3,
                className="mb-3",
            ),
        ]
    )


layout = dbc.Container(
    [
        dcc.Interval(id="news-lens-pca-load", interval=50, n_intervals=0, max_intervals=1),
        dcc.Interval(id="news-lens-temporal-play-interval", interval=1200, n_intervals=0, disabled=True),
        dcc.Store(id="news-lens-pca-cache"),
        dbc.Row([dbc.Col(html.H3("News Lens PCA", className="mb-2"), width=12)]),
        dbc.Row(
            [
                dbc.Col(
                    html.P(
                        "Principal Component Analysis and classical MDS over complete article-lens rows. "
                        "Use this page to inspect variance structure, identify the strongest lens drivers, "
                        "and compare source/article separation across two reduced-dimension projections.",
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
                            id="news-lens-pca-mode",
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
                        dcc.Input(id="news-lens-pca-snapshot-date", type="date", className="form-control", disabled=True),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Color by"),
                        dcc.Dropdown(
                            id="news-lens-pca-color-by",
                            options=[
                                {"label": "Source", "value": "source"},
                                {"label": "Strongest Lens", "value": "strongest_lens"},
                            ],
                            value="source",
                            clearable=False,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Max points"),
                        dcc.Dropdown(
                            id="news-lens-pca-max-points",
                            options=[{"label": str(n), "value": n} for n in (100, 200, 300, 500, 800)],
                            value=300,
                            clearable=False,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        dbc.Label("Actions"),
                        dbc.Button("Refresh", id="news-lens-pca-refresh", color="secondary"),
                    ],
                    md=1,
                ),
                dbc.Col(html.Div(id="news-lens-pca-status"), md=3),
            ],
            className="mb-3",
        ),
        dbc.Row(id="news-lens-pca-cards"),
        dbc.Row([dbc.Col(html.Div(id="news-lens-pca-separation"), width=12)]),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-lens-pca-explained"), lg=5, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-lens-pca-scatter"), lg=7, className="mb-3"),
            ]
        ),
        dbc.Row([dbc.Col(dcc.Graph(id="news-lens-mds-scatter"), width=12, className="mb-3")]),
        dbc.Row(
            [
                dbc.Col(dcc.Graph(id="news-lens-time-series"), lg=4, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-lens-temporal-embedding"), lg=4, className="mb-3"),
                dbc.Col(dcc.Graph(id="news-lens-temporal-embedding-mds"), lg=4, className="mb-3"),
            ]
        ),
        dbc.Row([dbc.Col(dcc.Graph(id="news-lens-temporal-diagnostics"), width=12, className="mb-3")]),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Temporal day window"),
                        dcc.Slider(
                            id="news-lens-temporal-day-slider",
                            min=0,
                            max=0,
                            value=0,
                            marks={0: "All"},
                            step=1,
                            updatemode="drag",
                            tooltip={"placement": "bottom", "always_visible": False},
                        ),
                    ],
                    md=9,
                    className="mb-3",
                ),
                dbc.Col(
                    [
                        dbc.Label("Playback"),
                        dbc.Button("Play", id="news-lens-temporal-play", color="secondary", className="w-100"),
                    ],
                    md=3,
                    className="mb-3",
                ),
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Playback speed"),
                        dcc.Dropdown(
                            id="news-lens-temporal-speed",
                            options=[
                                {"label": "0.5x", "value": 0.5},
                                {"label": "1x", "value": 1.0},
                                {"label": "2x", "value": 2.0},
                            ],
                            value=1.0,
                            clearable=False,
                        ),
                    ],
                    md=3,
                    className="mb-3",
                ),
                dbc.Col(
                    [
                        dbc.Label("Temporal mode"),
                        dcc.Dropdown(
                            id="news-lens-temporal-step-mode",
                            options=[
                                {"label": "Daily", "value": "daily"},
                                {"label": "Weekly", "value": "weekly"},
                            ],
                            value="daily",
                            clearable=False,
                        ),
                    ],
                    md=3,
                    className="mb-3",
                ),
                dbc.Col(
                    [
                        dbc.Label("Trailing window"),
                        dcc.Dropdown(
                            id="news-lens-temporal-window-days",
                            options=[
                                {"label": "All history", "value": 0},
                                {"label": "7 days", "value": 7},
                                {"label": "14 days", "value": 14},
                                {"label": "30 days", "value": 30},
                                {"label": "90 days", "value": 90},
                            ],
                            value=0,
                            clearable=False,
                        ),
                    ],
                    md=3,
                    className="mb-3",
                ),
            ]
        ),
        dbc.Row([dbc.Col(dcc.Graph(id="news-lens-pca-drivers"), width=12, className="mb-3")]),
        dbc.Row([dbc.Col(dcc.Graph(id="news-lens-pca-loadings"), width=12, className="mb-3")]),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Label("Component detail"),
                        dcc.Dropdown(id="news-lens-pca-component", options=[], value=None, clearable=False),
                    ],
                    md=3,
                    className="mb-3",
                )
            ]
        ),
        dbc.Row([dbc.Col(dcc.Graph(id="news-lens-pca-component-figure"), width=12, className="mb-3")]),
        dbc.Row([dbc.Col(html.Div(id="news-lens-pca-table"), width=12)]),
    ],
    fluid=True,
    className="py-4",
)


@callback(
    Output("news-lens-pca-cache", "data"),
    Output("news-lens-pca-status", "children"),
    Output("news-lens-pca-cards", "children"),
    Output("news-lens-pca-separation", "children"),
    Output("news-lens-pca-explained", "figure"),
    Output("news-lens-pca-scatter", "figure"),
    Output("news-lens-mds-scatter", "figure"),
    Output("news-lens-time-series", "figure"),
    Output("news-lens-temporal-embedding", "figure"),
    Output("news-lens-temporal-embedding-mds", "figure"),
    Output("news-lens-temporal-diagnostics", "figure"),
    Output("news-lens-pca-drivers", "figure"),
    Output("news-lens-pca-loadings", "figure"),
    Output("news-lens-pca-component", "options"),
    Output("news-lens-pca-component", "value"),
    Output("news-lens-pca-component-figure", "figure"),
    Output("news-lens-pca-table", "children"),
    Output("news-lens-temporal-play-interval", "disabled"),
    Output("news-lens-temporal-play-interval", "interval"),
    Output("news-lens-temporal-play", "children"),
    Output("news-lens-temporal-day-slider", "max"),
    Output("news-lens-temporal-day-slider", "marks"),
    Output("news-lens-temporal-day-slider", "step"),
    Output("news-lens-temporal-day-slider", "value"),
    Input("news-lens-pca-load", "n_intervals"),
    Input("news-lens-pca-refresh", "n_clicks"),
    Input("news-lens-pca-color-by", "value"),
    Input("news-lens-pca-max-points", "value"),
    Input("news-lens-temporal-play", "n_clicks"),
    Input("news-lens-temporal-play-interval", "n_intervals"),
    Input("news-lens-temporal-day-slider", "value"),
    Input("news-lens-temporal-speed", "value"),
    Input("news-lens-temporal-step-mode", "value"),
    Input("news-lens-temporal-window-days", "value"),
    Input("news-lens-pca-mode", "value"),
    Input("news-lens-pca-snapshot-date", "value"),
    State("news-lens-pca-component", "value"),
    State("news-lens-pca-cache", "data"),
)
def load_news_lens_pca(
    _load_tick,
    _refresh_clicks,
    color_by,
    max_points,
    play_clicks,
    play_tick,
    slider_value,
    temporal_speed,
    temporal_step_mode,
    trailing_window_days,
    data_mode,
    snapshot_date,
    selected_component,
    cached_bundle,
):
    trigger_id = ctx.triggered_id
    snapshot_key = str(snapshot_date or "")
    is_playing = bool((int(play_clicks) if isinstance(play_clicks, (int, float)) else 0) % 2 == 1)

    cached_payload = None
    if isinstance(cached_bundle, dict):
        cache_mode = str(cached_bundle.get("mode") or "")
        cache_snapshot = str(cached_bundle.get("snapshot_date") or "")
        candidate = cached_bundle.get("payload")
        if cache_mode == str(data_mode or "") and cache_snapshot == snapshot_key and isinstance(candidate, dict):
            cached_payload = candidate

    should_fetch = trigger_id in {
        "news-lens-pca-load",
        "news-lens-pca-refresh",
        "news-lens-pca-mode",
        "news-lens-pca-snapshot-date",
    } or not isinstance(cached_payload, dict)

    payload = cached_payload if isinstance(cached_payload, dict) else {}
    next_cache_bundle = cached_bundle
    if should_fetch:
        force_refresh = trigger_id == "news-lens-pca-refresh"
        status_code, payload = api_get(
            "/api/news/stats",
            {
                "snapshot_date": snapshot_param(data_mode, snapshot_date),
                "refresh": "true" if force_refresh else None,
            },
        )
    else:
        status_code = 200

    if status_code != 200:
        error = payload.get("error", "Unknown error")
        alert = dbc.Alert(f"Stats error ({status_code}): {error}", color="danger")
        empty = _empty_figure("No data")
        return (
            next_cache_bundle,
            alert,
            _summary_cards({}),
            dbc.Alert("No separation data", color="warning"),
            empty,
            empty,
            empty,
            empty,
            empty,
            empty,
            empty,
            empty,
            empty,
            [],
            None,
            empty,
            alert,
            True,
            1200,
            "Play",
            0,
            {0: "All"},
            1,
            0,
        )

    if should_fetch:
        next_cache_bundle = {
            "mode": str(data_mode or ""),
            "snapshot_date": snapshot_key,
            "payload": payload,
        }

    meta = payload.get("meta", {})
    data = payload.get("data", {})
    pca_payload, source = _select_lens_pca(data)
    mds_payload, mds_source = _select_lens_mds(data)
    separation_payload, separation_source = _select_lens_separation(data)
    time_series_payload, time_series_source = _select_lens_time_series(data)
    temporal_embedding_payload, temporal_embedding_source = _select_lens_temporal_embedding(data)
    temporal_embedding_mds_payload, temporal_embedding_mds_source = _select_lens_temporal_embedding_mds(data)
    pca_status = str(pca_payload.get("status") or "missing")
    pca_reason = str(pca_payload.get("reason") or "").strip()
    mds_status = str(mds_payload.get("status") or "missing")
    mds_reason = str(mds_payload.get("reason") or "").strip()
    leading_parts = [
        f"PCA source: {source}",
        f"PCA status: {pca_status}",
        f"Complete rows: {pca_payload.get('n_articles', 0)}",
        f"Lenses: {pca_payload.get('n_lenses', 0)}",
        f"Basis: {pca_payload.get('basis', 'n/a')}",
        f"MDS source: {mds_source}",
        f"MDS status: {mds_status}",
        f"Time-series source: {time_series_source}",
        f"Time-series status: {time_series_payload.get('status', 'missing')}",
        f"Temporal embedding source: {temporal_embedding_source}",
        f"Temporal embedding status: {temporal_embedding_payload.get('status', 'missing')}",
        f"Temporal MDS source: {temporal_embedding_mds_source}",
        f"Temporal MDS status: {temporal_embedding_mds_payload.get('status', 'missing')}",
        f"Separation source: {separation_source}",
        f"Separation status: {separation_payload.get('status', 'missing')}",
    ]
    if pca_reason:
        leading_parts.append(f"PCA reason: {pca_reason}")
    if mds_reason:
        leading_parts.append(f"MDS reason: {mds_reason}")
    status_alert = build_status_alert(meta, leading_parts=leading_parts)

    components = pca_payload.get("components") if isinstance(pca_payload.get("components"), list) else []
    component_options = [{"label": str(component), "value": str(component)} for component in components if isinstance(component, str)]
    option_values = {option["value"] for option in component_options}
    selected_value = selected_component if selected_component in option_values else (component_options[0]["value"] if component_options else None)
    point_limit = int(max_points) if isinstance(max_points, (int, float)) else 300
    color_mode = str(color_by or "source")
    step_size = 7 if str(temporal_step_mode or "daily") == "weekly" else 1
    slider_max, slider_marks, slider_day_value, slider_step = _temporal_slider_config(
        temporal_embedding_payload,
        temporal_embedding_mds_payload,
        int(slider_value) if isinstance(slider_value, (int, float)) else None,
        is_playing,
        int(play_tick) if isinstance(play_tick, (int, float)) else 0,
        step_size,
    )
    speed = float(temporal_speed) if isinstance(temporal_speed, (int, float)) else 1.0
    if speed <= 0.0:
        speed = 1.0
    play_interval_ms = max(250, int(1200 / speed))
    window_days = int(trailing_window_days) if isinstance(trailing_window_days, (int, float)) else 0
    window_days = window_days if window_days > 0 else None
    play_label = "Pause" if is_playing else "Play"

    return (
        next_cache_bundle,
        status_alert,
        _summary_cards(pca_payload),
        _separation_summary(separation_payload),
        _explained_variance_figure(pca_payload),
        _article_scatter_figure(pca_payload, color_mode, point_limit),
        _mds_scatter_figure(mds_payload, color_mode, point_limit),
        _lens_time_series_figure(time_series_payload),
        _temporal_embedding_figure(
            temporal_embedding_payload,
            slider_day_value,
            trailing_window_days=window_days,
            step_size=step_size,
        ),
        _temporal_embedding_mds_figure(
            temporal_embedding_mds_payload,
            slider_day_value,
            trailing_window_days=window_days,
            step_size=step_size,
        ),
        _temporal_diagnostics_figure(
            temporal_embedding_payload,
            temporal_embedding_mds_payload,
            slider_day_value,
            trailing_window_days=window_days,
            step_size=step_size,
        ),
        _variance_driver_figure(pca_payload),
        _loadings_heatmap_figure(pca_payload),
        component_options,
        selected_value,
        _component_loading_figure(pca_payload, selected_value),
        _component_table(pca_payload),
        not is_playing,
        play_interval_ms,
        play_label,
        slider_max,
        slider_marks,
        slider_step,
        slider_day_value,
    )


@callback(
    Output("news-lens-pca-snapshot-date", "disabled"),
    Input("news-lens-pca-mode", "value"),
)
def toggle_news_lens_pca_snapshot_input(data_mode):
    return data_mode != "snapshot"
