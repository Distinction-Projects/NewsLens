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
  const data = payload?.data || {};
  const derived = data?.derived || {};
  const meta = payload?.meta || {};
  const summary = data?.summary || {};
  const scoreStatus = derived?.score_status || {};
  const sourceCounts = asArray(derived.source_counts).slice(0, 15);
  const tagCounts = asArray(derived.tag_counts).slice(0, 15);
  const dailyCounts = asArray(derived.daily_counts_utc);
  const statusRows = [
    { label: "Scored", value: toNumber(scoreStatus.scored) || 0 },
    { label: "Positive", value: toNumber(scoreStatus.positive) || 0 },
    { label: "Zero", value: toNumber(scoreStatus.zero) || 0 },
    { label: "Unscorable", value: toNumber(scoreStatus.unscorable) || 0 }
  ];

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Coverage Snapshot</h3>
        <p className="muted">
          Source mode: <code>{meta.source_mode || "unknown"}</code>
        </p>
        <div className="stats-grid">
          <div className="stat-card">
            <span className="muted">Total Articles</span>
            <strong>{formatNumber(derived.total_articles ?? summary.articles)}</strong>
          </div>
          <div className="stat-card">
            <span className="muted">Scored Articles</span>
            <strong>{formatNumber(derived.scored_articles ?? summary.scored_articles)}</strong>
          </div>
          <div className="stat-card">
            <span className="muted">Coverage</span>
            <strong>{formatPercent(derived.score_coverage_ratio)}</strong>
          </div>
          <div className="stat-card">
            <span className="muted">Sources</span>
            <strong>{formatNumber(Array.isArray(derived.source_counts) ? derived.source_counts.length : 0)}</strong>
          </div>
        </div>
      </div>

      <div className="panel">
        <h3>Score Status</h3>
        <div className="chart-grid">
          <PlotlyChart
            data={[
              {
                type: "bar",
                x: sourceCounts.map((row) => String(row.source || "Unknown")),
                y: sourceCounts.map((row) => toNumber(row.count) || 0),
                marker: { color: "#4fd1c5" }
              }
            ]}
            layout={{ title: "Article Volume by Source", yaxis: { title: "Articles" } }}
          />
          <PlotlyChart
            data={[
              {
                type: "bar",
                x: tagCounts.map((row) => String(row.tag || "Unknown")),
                y: tagCounts.map((row) => toNumber(row.count) || 0),
                marker: { color: "#fd7e14" }
              }
            ]}
            layout={{ title: "Top Tags", yaxis: { title: "Count" } }}
          />
          <PlotlyChart
            data={[
              {
                type: "bar",
                x: statusRows.map((row) => row.label),
                y: statusRows.map((row) => row.value),
                marker: { color: "#7aa7ff" }
              }
            ]}
            layout={{ title: "Score Status Counts", yaxis: { title: "Articles" } }}
          />
          <PlotlyChart
            data={[
              {
                type: "scatter",
                mode: "lines+markers",
                x: dailyCounts.map((row) => String(row.date || "")),
                y: dailyCounts.map((row) => toNumber(row.count) || 0),
                line: { color: "#9d7dff" }
              }
            ]}
            layout={{ title: "Daily Articles (UTC)", yaxis: { title: "Articles" } }}
          />
        </div>
        <table className="news-table compact">
          <tbody>
            <tr>
              <th>Scored</th>
              <td>{formatNumber(scoreStatus.scored)}</td>
            </tr>
            <tr>
              <th>Positive</th>
              <td>{formatNumber(scoreStatus.positive)}</td>
            </tr>
            <tr>
              <th>Zero</th>
              <td>{formatNumber(scoreStatus.zero)}</td>
            </tr>
            <tr>
              <th>Unscorable</th>
              <td>{formatNumber(scoreStatus.unscorable)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}
