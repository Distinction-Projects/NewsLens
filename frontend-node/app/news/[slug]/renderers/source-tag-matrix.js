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
  const sourceLabels = asArray(sourceTagViews.source_labels).slice(0, 10);
  const tagLabels = asArray(sourceTagViews.tag_labels).slice(0, 10);
  const matrixRows = asArray(chartAggregates.source_tag_matrix);
  const sourceTotals = asArray(chartAggregates.source_tag_totals).slice(0, 12);
  const lookup = new Map(
    matrixRows.map((row) => [pairKey(row.source, row.tag), toNumber(row.count) || 0])
  );
  const matrix = sourceLabels.map((source) => tagLabels.map((tag) => lookup.get(pairKey(source, tag)) || 0));

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Matrix Visuals</h3>
        {sourceLabels.length === 0 || tagLabels.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
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
              layout={{ title: "Source x Tag Intensity Heatmap" }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: sourceTotals.map((row) => String(row.source || "Unknown")),
                  y: sourceTotals.map((row) => toNumber(row.count) || 0),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Source Tag Totals", yaxis: { title: "Tag Assignments" } }}
            />
          </div>
        )}
      </div>
      <div className="panel">
        <h3>Source x Tag Matrix</h3>
        <p className="muted">Showing the top {formatNumber(sourceLabels.length)} sources and top {formatNumber(tagLabels.length)} tags.</p>
        {sourceLabels.length === 0 || tagLabels.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="table-scroll">
            <table className="news-table">
              <thead>
                <tr>
                  <th>Source</th>
                  {tagLabels.map((tag) => (
                    <th key={tag}>{tag}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sourceLabels.map((source) => (
                  <tr key={source}>
                    <td>{source}</td>
                    {tagLabels.map((tag) => (
                      <td key={`${source}-${tag}`}>{formatNumber(lookup.get(pairKey(source, tag)) || 0)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Source Tag Totals</h3>
        {sourceTotals.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Source</th>
                <th>Tag Assignments</th>
              </tr>
            </thead>
            <tbody>
              {sourceTotals.map((row) => (
                <tr key={String(row.source || "unknown")}>
                  <td>{row.source || "Unknown"}</td>
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
