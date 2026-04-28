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
  const correlations = asObject(derived.lens_correlations);
  const lenses = asArray(correlations.lenses);
  const corrRaw = asArray(asObject(correlations.correlation).raw);
  const pairRankings = asArray(asObject(correlations.pair_rankings).corr_raw);
  const rawTopPairs =
    pairRankings.length > 0
      ? pairRankings
          .map((row) => ({
            lens_a: row?.lens_a,
            lens_b: row?.lens_b,
            value: toNumber(row?.value)
          }))
          .filter((row) => row.lens_a && row.lens_b && row.value !== null)
      : getCorrelationPairRows(lenses, corrRaw);
  const topPairs = rawTopPairs.slice(0, 25);
  const matrix = lenses.map((_, rowIndex) =>
    lenses.map((_, colIndex) => toNumber(asArray(corrRaw[rowIndex])[colIndex]) || 0)
  );

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Correlation Summary</h3>
        <div className="stats-grid">
          <StatCard label="Lenses" value={formatNumber(lenses.length)} />
          <StatCard label="Pairs" value={formatNumber(topPairs.length)} />
          <StatCard label="Matrixes" value="corr/cov/pairwise" />
        </div>
      </div>

      <div className="panel">
        <h3>Correlation Visuals</h3>
        {lenses.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "heatmap",
                  x: lenses,
                  y: lenses,
                  z: matrix,
                  zmin: -1,
                  zmax: 1,
                  colorscale: "RdBu"
                }
              ]}
              layout={{ title: "Lens Correlation Heatmap (Raw)" }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  orientation: "h",
                  y: topPairs
                    .map((row) => `${row.lens_a} vs ${row.lens_b}`)
                    .reverse(),
                  x: topPairs.map((row) => toNumber(row.value) || 0).reverse(),
                  marker: {
                    color: topPairs.map((row) => (toNumber(row.value) || 0)).reverse(),
                    colorscale: "RdBu"
                  }
                }
              ]}
              layout={{ title: "Top Correlation Pairs (Signed)", xaxis: { title: "Correlation" } }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Top Lens Pairs (Correlation Raw)</h3>
        {rawTopPairs.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Lens A</th>
                <th>Lens B</th>
                <th>Correlation</th>
              </tr>
            </thead>
            <tbody>
              {rawTopPairs.slice(0, 25).map((row, index) => (
                <tr key={`${row.lens_a}-${row.lens_b}-${index}`}>
                  <td>{row.lens_a}</td>
                  <td>{row.lens_b}</td>
                  <td>{formatDecimal(row.value, 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
