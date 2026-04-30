import { fetchNewsJson, newsApiBaseUrl } from "../../../../lib/newsApi";
import {
  activeSnapshotDate,
  asArray,
  asObject,
  buildQueryHref,
  fetchStatsForMode,
  formatAlreadyPercent,
  formatDecimal,
  formatNumber,
  formatPercent,
  getQueryParam,
  getStatsDerived,
  isTruthyQueryValue,
  normalizeDataMode,
  queryLimit,
  selectedSnapshotDateValue,
  snapshotDateFromSearchParams,
  toNumber,
  truncateText
} from "../../../../lib/newsPageUtils";
import PlotlyChart from "../../../../components/PlotlyChart";
import {
  DataModeControls,
  EmptyState,
  MiniBar,
  SectionHeader,
  StatCard,
  StatusBlock,
  StatusPill
} from "../../../../components/news/NewsDashboardPrimitives";
import {
  EndpointTable,
  extractSnapshotMetrics,
  fetchEndpointStatus,
  getCorrelationPairRows,
  metricDelta,
  pairKey
} from "./shared";

function topRecentSourceLabel(row) {
  const source = asArray(row?.top_recent_sources)[0];
  if (!source) {
    return "n/a";
  }
  return `${source.source || "Unknown"} (${formatNumber(source.count)})`;
}

export async function render(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const chartAggregates = asObject(derived.chart_aggregates);
  const sourceTagViews = asObject(derived.source_tag_views);
  const tagMomentum = asObject(derived.tag_momentum);
  const tagMomentumSummary = asObject(tagMomentum.summary);
  const tagMomentumRows = asArray(tagMomentum.rows).slice(0, 20);
  const tagCounts = asArray(derived.tag_counts).slice(0, 30);
  const tagDistribution = asArray(chartAggregates.tag_count_distribution);
  const sourceTagMatrixRows = asArray(chartAggregates.source_tag_matrix);
  const sourceLabels = asArray(sourceTagViews.source_labels).slice(0, 10);
  const tagLabels = asArray(sourceTagViews.tag_labels).slice(0, 12);
  const matrixLookup = new Map(
    sourceTagMatrixRows.map((row) => [pairKey(row.source, row.tag), toNumber(row.count) || 0])
  );
  const matrix = sourceLabels.map((source) => tagLabels.map((tag) => matrixLookup.get(pairKey(source, tag)) || 0));
  const maxTagCount = tagCounts.reduce((max, row) => Math.max(max, toNumber(row.count) || 0), 0);
  const maxMomentumScore = tagMomentumRows.reduce((max, row) => Math.max(max, toNumber(row.momentum_score) || 0), 0);

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <SectionHeader
          kicker="Momentum"
          title="Tags Blowing Up"
          summary="Ranks tags with exponential time decay plus recent-vs-baseline lift, so currently active or newly surging topics rise above historically common tags."
        />
        <StatusBlock status={String(tagMomentum.status || "unavailable")} reason={String(tagMomentum.reason || "")} />
        <div className="stats-grid">
          <StatCard label="Reference Date" value={tagMomentumSummary.reference_date || "n/a"} />
          <StatCard label="Recent Articles" value={formatNumber(tagMomentumSummary.recent_articles)} />
          <StatCard label="Baseline Articles" value={formatNumber(tagMomentumSummary.baseline_articles)} />
          <StatCard label="New Tags" value={formatNumber(tagMomentumSummary.new_tag_count)} />
          <StatCard label="Accelerating Tags" value={formatNumber(tagMomentumSummary.accelerating_tag_count)} />
        </div>
        {tagMomentumRows.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            <div className="chart-grid">
              <PlotlyChart
                data={[
                  {
                    type: "bar",
                    orientation: "h",
                    y: tagMomentumRows.map((row) => String(row.tag || "Unknown")).reverse(),
                    x: tagMomentumRows.map((row) => toNumber(row.momentum_score) || 0).reverse(),
                    customdata: tagMomentumRows
                      .map((row) => [
                        toNumber(row.recent_count) || 0,
                        toNumber(row.baseline_count) || 0,
                        toNumber(row.lift_ratio),
                        String(row.trend || "")
                      ])
                      .reverse(),
                    hovertemplate:
                      "%{y}<br>Momentum: %{x:.2f}<br>Recent: %{customdata[0]}<br>Baseline: %{customdata[1]}<br>Lift: %{customdata[2]:.2f}x<br>Trend: %{customdata[3]}<extra></extra>",
                    marker: {
                      color: tagMomentumRows
                        .map((row) => {
                          const trend = String(row.trend || "");
                          if (trend === "new") return "#f0b36f";
                          if (trend === "accelerating") return "#4fd1c5";
                          if (trend === "active") return "#7aa7ff";
                          return "#8ca0bf";
                        })
                        .reverse()
                    }
                  }
                ]}
                layout={{ title: "Tag Momentum Score", xaxis: { title: "Decayed score with lift bonus" } }}
              />
              <PlotlyChart
                data={[
                  {
                    type: "scatter",
                    mode: "markers+text",
                    x: tagMomentumRows.map((row) => toNumber(row.recent_count) || 0),
                    y: tagMomentumRows.map((row) => toNumber(row.lift_ratio) || 0),
                    text: tagMomentumRows.map((row) => String(row.tag || "")),
                    textposition: "top center",
                    customdata: tagMomentumRows.map((row) => [toNumber(row.momentum_score), String(row.trend || "")]),
                    hovertemplate:
                      "%{text}<br>Recent count: %{x}<br>Lift: %{y:.2f}x<br>Momentum: %{customdata[0]:.2f}<br>Trend: %{customdata[1]}<extra></extra>",
                    marker: {
                      size: tagMomentumRows.map((row) => Math.max(8, Math.min(28, Math.sqrt(toNumber(row.momentum_score) || 1) * 5))),
                      color: "#4fd1c5",
                      opacity: 0.78
                    }
                  }
                ]}
                layout={{ title: "Recent Count vs Baseline Lift", xaxis: { title: "Recent articles" }, yaxis: { title: "Recent share / baseline share" } }}
              />
            </div>
            <div className="table-scroll">
              <table className="news-table">
                <thead>
                  <tr>
                    <th>Tag</th>
                    <th>Trend</th>
                    <th>Momentum</th>
                    <th>Recent</th>
                    <th>Baseline</th>
                    <th>Recent Sources</th>
                    <th>Top Recent Source</th>
                    <th>Lift</th>
                    <th>Latest Seen</th>
                    <th>Relative Momentum</th>
                  </tr>
                </thead>
                <tbody>
                  {tagMomentumRows.map((row) => (
                    <tr key={String(row.tag || "unknown")}>
                      <td>{row.tag || "Unknown"}</td>
                      <td>
                        <StatusPill tone={String(row.trend || "") === "cooling" ? "bad" : "good"}>{row.trend || "n/a"}</StatusPill>
                      </td>
                      <td>{formatDecimal(row.momentum_score, 2)}</td>
                      <td>{formatNumber(row.recent_count)}</td>
                      <td>{formatNumber(row.baseline_count)}</td>
                      <td>{formatNumber(row.recent_source_count)}</td>
                      <td>{topRecentSourceLabel(row)}</td>
                      <td>{row.lift_ratio === null || row.lift_ratio === undefined ? "new" : `${formatDecimal(row.lift_ratio, 2)}x`}</td>
                      <td>{row.latest_seen || "n/a"}</td>
                      <td>
                        <MiniBar value={row.momentum_score} max={maxMomentumScore} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      <div className="panel">
        <h3>Top Tags</h3>
        {tagCounts.length > 0 ? (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  orientation: "h",
                  y: tagCounts.map((row) => String(row.tag || "Unknown")).reverse(),
                  x: tagCounts.map((row) => toNumber(row.count) || 0).reverse(),
                  marker: { color: "#fd7e14" }
                }
              ]}
              layout={{ title: "Top Tags", xaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: tagDistribution.map((row) => String(row.label || "Unknown")),
                  y: tagDistribution.map((row) => toNumber(row.count) || 0),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Tags per Article Distribution", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "heatmap",
                  x: tagLabels,
                  y: sourceLabels,
                  z: matrix,
                  colorscale: "Viridis"
                }
              ]}
              layout={{ title: "Source x Tag Intensity" }}
            />
          </div>
        ) : null}
        {tagCounts.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table">
            <thead>
              <tr>
                <th>Tag</th>
                <th>Articles</th>
                <th>Relative Frequency</th>
              </tr>
            </thead>
            <tbody>
              {tagCounts.map((row) => (
                <tr key={String(row.tag || "unknown")}>
                  <td>{row.tag || "Unknown"}</td>
                  <td>{formatNumber(row.count)}</td>
                  <td>
                    <MiniBar value={row.count} max={maxTagCount} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Tags Per Article</h3>
        {tagDistribution.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Bucket</th>
                <th>Articles</th>
              </tr>
            </thead>
            <tbody>
              {tagDistribution.map((row) => (
                <tr key={String(row.label)}>
                  <td>{row.label}</td>
                  <td>{formatNumber(row.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
