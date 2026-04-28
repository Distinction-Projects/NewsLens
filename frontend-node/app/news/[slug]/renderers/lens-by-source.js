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
  const lensNames = asArray(lensViews.lens_names);
  const sourceRows = asArray(lensViews.source_rows).slice(0, 20);
  const summary = asObject(lensViews.summary);
  const sourceLensAverageRows = asArray(summary.source_lens_average_rows)
    .map((row) => ({
      lens: String(row?.lens || ""),
      mean: toNumber(row?.mean)
    }))
    .filter((row) => row.lens && row.mean !== null)
    .sort((a, b) => (b.mean || 0) - (a.mean || 0));
  const focusLens = sourceLensAverageRows[0]?.lens || lensNames[0] || null;
  const matrix = sourceRows.map((row) => {
    const means = asObject(row.lens_means);
    return lensNames.map((lens) => toNumber(means[lens]) || 0);
  });

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Source x Lens Matrix</h3>
        <div className="stats-grid">
          <StatCard label="Sources" value={formatNumber(sourceRows.length)} />
          <StatCard label="Lenses" value={formatNumber(lensNames.length)} />
          <StatCard label="Coverage Mode" value={lensViews.coverage_mode || "n/a"} />
        </div>
      </div>

      <div className="panel">
        <h3>Lens-by-Source Visuals</h3>
        {sourceRows.length === 0 || lensNames.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "heatmap",
                  x: lensNames,
                  y: sourceRows.map((row) => String(row.source || "Unknown")),
                  z: matrix,
                  colorscale: "Viridis"
                }
              ]}
              layout={{ title: "Source x Lens Mean Heatmap" }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: sourceRows.map((row) => String(row.source || "Unknown")),
                  y: sourceRows.map((row) => {
                    const means = asObject(row.lens_means);
                    return focusLens ? toNumber(means[focusLens]) || 0 : 0;
                  }),
                  marker: { color: "#fd7e14" }
                }
              ]}
              layout={{ title: `Source Comparison for Focus Lens: ${focusLens || "n/a"}`, yaxis: { title: "Percent" } }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Lens Means by Source</h3>
        {sourceRows.length === 0 || lensNames.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="table-scroll">
            <table className="news-table compact">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Articles</th>
                  {lensNames.map((lens) => (
                    <th key={lens}>{lens}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sourceRows.map((row) => {
                  const means = asObject(row.lens_means);
                  return (
                    <tr key={String(row.source || "unknown")}>
                      <td>{row.source || "Unknown"}</td>
                      <td>{formatNumber(row.article_count)}</td>
                      {lensNames.map((lens) => (
                        <td key={`${row.source}-${lens}`}>{formatAlreadyPercent(means[lens])}</td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
