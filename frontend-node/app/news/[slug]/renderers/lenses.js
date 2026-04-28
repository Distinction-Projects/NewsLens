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
  const lensInventory = asObject(derived.lens_inventory || asObject(payload?.data?.analysis).lens_summary);
  const lenses = asArray(lensInventory.lenses);
  const itemsTotal = toNumber(lensInventory.items_total);
  const avgRubrics =
    lenses.length > 0
      ? lenses.reduce((sum, row) => sum + (toNumber(row.rubric_count) || 0), 0) / lenses.length
      : null;
  const avgMaxScore =
    lenses.length > 0 ? lenses.reduce((sum, row) => sum + (toNumber(row.max_total) || 0), 0) / lenses.length : null;
  const lensRows = lenses.slice(0, 20).map((row) => {
    const scoredItems = toNumber(row.items_with_scores) || 0;
    const coverage = itemsTotal && scoredItems !== null ? (scoredItems / itemsTotal) * 100 : 0;
    return {
      name: String(row.name || "Unknown Lens"),
      maxTotal: toNumber(row.max_total) || 0,
      coverage
    };
  });

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Lens Inventory</h3>
        <p className="muted">
          Coverage mode: <code>{lensInventory.coverage_mode || "unknown"}</code>
        </p>
        <div className="stats-grid">
          <StatCard label="Tracked Lenses" value={formatNumber(lenses.length)} />
          <StatCard label="Scored Items" value={formatNumber(itemsTotal)} />
          <StatCard label="Aggregation" value={lensInventory.aggregation || "n/a"} />
          <StatCard label="Avg Rubrics / Lens" value={formatDecimal(avgRubrics, 1)} />
          <StatCard label="Avg Max Score" value={formatDecimal(avgMaxScore, 1)} />
        </div>
      </div>

      <div className="panel">
        <h3>Lens Coverage</h3>
        {lensRows.length > 0 ? (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: lensRows.map((row) => row.name),
                  y: lensRows.map((row) => row.maxTotal),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Lens Maximum Score Capacity", yaxis: { title: "Max Score" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: lensRows.map((row) => row.name),
                  y: lensRows.map((row) => row.coverage),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Lens Coverage Across Articles (%)", yaxis: { title: "Coverage %", range: [0, 100] } }}
            />
          </div>
        ) : null}
        {lenses.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table">
            <thead>
              <tr>
                <th>Lens</th>
                <th>Rubrics</th>
                <th>Max Total</th>
                <th>Items with Scores</th>
                <th>Coverage</th>
              </tr>
            </thead>
            <tbody>
              {lenses.map((row) => {
                const name = String(row.name || "Unknown Lens");
                const scoredItems = toNumber(row.items_with_scores);
                const coverage = itemsTotal && scoredItems !== null ? scoredItems / itemsTotal : null;
                return (
                  <tr key={name}>
                    <td>{name}</td>
                    <td>{formatNumber(row.rubric_count)}</td>
                    <td>{formatDecimal(row.max_total, 1)}</td>
                    <td>{formatNumber(scoredItems)}</td>
                    <td>
                      {formatPercent(coverage)}
                      <MiniBar value={coverage || 0} max={1} />
                    </td>
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
