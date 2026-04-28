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
  const summary = asObject(lensViews.summary);
  const articleRows = asArray(lensViews.article_rows).slice(0, 40);
  const sourceRows = asArray(lensViews.source_rows).slice(0, 20);
  const dominantLensCounts = asArray(summary.dominant_lens_counts).slice(0, 12);
  const largestGapRows = articleRows
    .map((row) => ({
      title: truncateText(row?.title || "Untitled", 44),
      gap: toNumber(row?.gap_vs_runner_up)
    }))
    .filter((row) => row.gap !== null)
    .sort((a, b) => (b.gap || 0) - (a.gap || 0))
    .slice(0, 12);

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Lens Explorer Summary</h3>
        <div className="stats-grid">
          <StatCard label="Coverage Mode" value={lensViews.coverage_mode || "n/a"} />
          <StatCard label="Articles with Lens Scores" value={formatNumber(summary.article_count)} />
          <StatCard label="Sources" value={formatNumber(summary.source_count)} />
          <StatCard label="Most Common Strongest Lens" value={summary.top_dominant_lens || "n/a"} />
        </div>
      </div>

      <div className="panel">
        <h3>Explorer Visuals</h3>
        {dominantLensCounts.length === 0 && largestGapRows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: dominantLensCounts.map((row) => String(row?.lens || "Unknown")),
                  y: dominantLensCounts.map((row) => toNumber(row?.count) || 0),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Strongest Lens Frequency", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: largestGapRows.map((row) => row.title),
                  y: largestGapRows.map((row) => row.gap || 0),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Largest Strongest-vs-Runner-Up Gaps", yaxis: { title: "Gap" } }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Article Lens Rows</h3>
        {articleRows.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Title</th>
                <th>Source</th>
                <th>Strongest Lens</th>
                <th>Strongest %</th>
                <th>Gap vs Runner-up</th>
              </tr>
            </thead>
            <tbody>
              {articleRows.map((row, index) => (
                <tr key={`${String(row.title || "untitled")}-${index}`}>
                  <td>{truncateText(row.title || "Untitled", 90)}</td>
                  <td>{row.source || "Unknown"}</td>
                  <td>{row.strongest_lens || "n/a"}</td>
                  <td>{formatAlreadyPercent(row.strongest_percent)}</td>
                  <td>{formatDecimal(row.gap_vs_runner_up, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Source Lens Means</h3>
        {sourceRows.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Source</th>
                <th>Articles</th>
                <th>Strongest Lens</th>
                <th>Strongest Gap</th>
              </tr>
            </thead>
            <tbody>
              {sourceRows.map((row) => (
                <tr key={String(row.source || "unknown")}>
                  <td>{row.source || "Unknown"}</td>
                  <td>{formatNumber(row.article_count)}</td>
                  <td>{row.strongest_lens || "n/a"}</td>
                  <td>{formatDecimal(row.strongest_gap, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
