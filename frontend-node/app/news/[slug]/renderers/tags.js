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

export async function render(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const chartAggregates = asObject(derived.chart_aggregates);
  const sourceTagViews = asObject(derived.source_tag_views);
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

  return (
    <>
      <DataModeControls searchParams={searchParams} />
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
