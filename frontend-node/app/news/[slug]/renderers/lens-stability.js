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
  const lensViews = asObject(derived.lens_views);
  const stabilityRows = asArray(lensViews.stability_rows);
  const summary = asObject(lensViews.summary);
  const scatterRows = stabilityRows
    .map((row) => ({
      lens: String(row?.lens || "Unknown"),
      mean: toNumber(row?.mean),
      stddev: toNumber(row?.stddev)
    }))
    .filter((row) => row.mean !== null && row.stddev !== null);
  const sourceGapRows = stabilityRows
    .map((row) => ({
      lens: String(row?.lens || "Unknown"),
      sourceGap: toNumber(row?.source_gap)
    }))
    .filter((row) => row.sourceGap !== null)
    .sort((a, b) => (b.sourceGap || 0) - (a.sourceGap || 0))
    .slice(0, 20);

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Stability Summary</h3>
        <div className="stats-grid">
          <StatCard label="Lenses Analyzed" value={formatNumber(summary.stability_lens_count)} />
          <StatCard label="Avg Std Dev" value={formatDecimal(summary.stability_avg_stddev, 2)} />
          <StatCard label="Most Volatile Lens" value={summary.stability_top_lens || "n/a"} />
          <StatCard label="Total Samples" value={formatNumber(summary.stability_total_samples)} />
        </div>
      </div>

      <div className="panel">
        <h3>Stability Visuals</h3>
        {scatterRows.length === 0 && sourceGapRows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "scatter",
                  mode: "markers+text",
                  x: scatterRows.map((row) => row.mean),
                  y: scatterRows.map((row) => row.stddev),
                  text: scatterRows.map((row) => row.lens),
                  textposition: "top center",
                  marker: { color: "#4fd1c5", size: 10 }
                }
              ]}
              layout={{ title: "Lens Mean vs Std Dev", xaxis: { title: "Mean" }, yaxis: { title: "Std Dev" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  orientation: "h",
                  y: sourceGapRows.map((row) => row.lens).reverse(),
                  x: sourceGapRows.map((row) => row.sourceGap || 0).reverse(),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Top Source Gaps by Lens", xaxis: { title: "Source Gap" } }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Lens Stability Table</h3>
        {stabilityRows.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Lens</th>
                <th>Samples</th>
                <th>Mean</th>
                <th>Std Dev</th>
                <th>CV %</th>
                <th>Source Gap</th>
                <th>Range</th>
              </tr>
            </thead>
            <tbody>
              {stabilityRows.slice(0, 30).map((row) => (
                <tr key={String(row.lens || "unknown")}>
                  <td>{row.lens || "Unknown"}</td>
                  <td>{formatNumber(row.count)}</td>
                  <td>{formatDecimal(row.mean, 2)}</td>
                  <td>{formatDecimal(row.stddev, 2)}</td>
                  <td>{formatDecimal(row.cv_percent, 2)}</td>
                  <td>{formatDecimal(row.source_gap, 2)}</td>
                  <td>{formatDecimal(row.range, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
