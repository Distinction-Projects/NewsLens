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
  const derived = payload?.data?.derived || {};
  const sourceCounts = Array.isArray(derived?.source_counts) ? derived.source_counts : [];
  const scoredBySource = Array.isArray(derived?.chart_aggregates?.scored_by_source)
    ? derived.chart_aggregates.scored_by_source
    : [];

  const scoredLookup = new Map(
    scoredBySource
      .filter((row) => row && typeof row === "object")
      .map((row) => [String(row.source || ""), Number(row.count || 0)])
  );
  const chartRows = sourceCounts.slice(0, 20).map((row) => {
    const source = String(row.source || "Unknown");
    const count = Number(row.count || 0);
    const scored = scoredLookup.get(source) || 0;
    return {
      source,
      count,
      scored,
      coverage: count > 0 ? (scored / count) * 100 : 0
    };
  });

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Source Charts</h3>
        {chartRows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: chartRows.map((row) => row.source),
                  y: chartRows.map((row) => row.count),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Article Volume by Source", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: chartRows.map((row) => row.source),
                  y: chartRows.map((row) => row.coverage),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Scoring Coverage by Source (%)", yaxis: { title: "Coverage %", range: [0, 100] } }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Source Coverage</h3>
        {sourceCounts.length === 0 ? (
          <p className="muted">No source data available.</p>
        ) : (
          <table className="news-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Articles</th>
                <th>Scored</th>
                <th>Coverage</th>
              </tr>
            </thead>
            <tbody>
              {sourceCounts.map((row) => {
                const source = String(row.source || "Unknown");
                const count = Number(row.count || 0);
                const scored = scoredLookup.get(source) || 0;
                const coverage = count > 0 ? scored / count : null;
                return (
                  <tr key={source}>
                    <td>{source}</td>
                    <td>{formatNumber(count)}</td>
                    <td>{formatNumber(scored)}</td>
                    <td>{coverage === null ? "n/a" : `${(coverage * 100).toFixed(1)}%`}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
