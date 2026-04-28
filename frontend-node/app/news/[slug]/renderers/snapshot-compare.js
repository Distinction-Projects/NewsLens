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
  const snapshotDate = snapshotDateFromSearchParams(searchParams);
  const snapshotInputValue = selectedSnapshotDateValue(searchParams);
  const forceRefresh = isTruthyQueryValue(getQueryParam(searchParams, "refresh"));
  const refreshHref = buildQueryHref({ snapshot: snapshotInputValue, refresh: "1" });
  const applyHref = buildQueryHref({ snapshot: snapshotInputValue, refresh: "" });
  if (!snapshotDate) {
    return (
      <>
        <div className="panel">
          <h3>Snapshot Compare Controls</h3>
          <form method="get" className="news-filter-grid">
            <label className="muted">
              Snapshot date (UTC)
              <input name="snapshot" type="date" defaultValue={snapshotInputValue} />
            </label>
            <div style={{ display: "flex", alignItems: "end", gap: "10px" }}>
              <button type="submit" className="news-nav-link">
                Run Compare
              </button>
            </div>
          </form>
        </div>
        <div className="panel">
          <h3>Snapshot Compare</h3>
          <p className="muted">Select a snapshot date to compare current vs historical metrics.</p>
        </div>
      </>
    );
  }

  const [currentPayload, snapshotPayload] = await Promise.all([
    fetchNewsJson(`/api/news/stats${forceRefresh ? "?refresh=true" : ""}`, forceRefresh ? { cache: "no-store" } : {}),
    fetchNewsJson(
      `/api/news/stats?snapshot_date=${encodeURIComponent(snapshotDate)}${forceRefresh ? "&refresh=true" : ""}`,
      forceRefresh ? { cache: "no-store" } : {}
    )
  ]);
  const currentMetrics = extractSnapshotMetrics(currentPayload);
  const snapshotMetrics = extractSnapshotMetrics(snapshotPayload);
  const currentMeta = asObject(currentPayload?.meta);
  const snapshotMeta = asObject(snapshotPayload?.meta);
  const rows = [
    ["Total Articles", "total_articles"],
    ["Scored Articles", "scored_articles"],
    ["Zero Scores", "zero_score_articles"],
    ["Unscorable", "unscorable_articles"],
    ["Score Coverage %", "score_coverage_ratio_percent"],
    ["Source Count", "source_count"],
    ["Tag Count", "tag_count"],
    ["Days Covered", "days_covered"]
  ];
  const chartRows = rows
    .map(([label, key]) => ({
      label,
      current: toNumber(currentMetrics[key]),
      snapshot: toNumber(snapshotMetrics[key])
    }))
    .filter((row) => row.current !== null && row.snapshot !== null);

  return (
    <>
      <div className="panel">
        <h3>Snapshot Compare Controls</h3>
        <form method="get" className="news-filter-grid">
          <label className="muted">
            Snapshot date (UTC)
            <input name="snapshot" type="date" defaultValue={snapshotDate} />
          </label>
          <div style={{ display: "flex", alignItems: "end", gap: "10px" }}>
            <button type="submit" className="news-nav-link">
              Run Compare
            </button>
            <a href={refreshHref} className="news-nav-link">
              Refresh
            </a>
          </div>
        </form>
        <p className="muted" style={{ marginTop: "10px" }}>
          Current generated: <strong>{currentMeta.generated_at || "n/a"}</strong> | Snapshot generated:{" "}
          <strong>{snapshotMeta.generated_at || "n/a"}</strong> | <a href={applyHref}>Clear refresh flag</a>
        </p>
      </div>
      <div className="panel">
        <h3>Snapshot Comparison Visual</h3>
        {chartRows.length === 0 ? (
          <EmptyState />
        ) : (
          <PlotlyChart
            data={[
              {
                type: "bar",
                name: "Current",
                x: chartRows.map((row) => row.label),
                y: chartRows.map((row) => row.current || 0),
                marker: { color: "#4fd1c5" }
              },
              {
                type: "bar",
                name: `Snapshot (${snapshotDate})`,
                x: chartRows.map((row) => row.label),
                y: chartRows.map((row) => row.snapshot || 0),
                marker: { color: "#7aa7ff" }
              }
            ]}
            layout={{ title: `Current vs Snapshot (${snapshotDate})`, barmode: "group", yaxis: { title: "Value" } }}
          />
        )}
      </div>
      <div className="panel">
        <h3>Current vs Snapshot ({snapshotDate})</h3>
        <table className="news-table compact">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Current</th>
              <th>Snapshot</th>
              <th>Delta</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, key]) => (
              <tr key={key}>
                <td>{label}</td>
                <td>{formatDecimal(currentMetrics[key], key.includes("ratio") ? 1 : 0)}</td>
                <td>{formatDecimal(snapshotMetrics[key], key.includes("ratio") ? 1 : 0)}</td>
                <td>{metricDelta(currentMetrics[key], snapshotMetrics[key])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
