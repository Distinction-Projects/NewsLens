import {
  asArray,
  asObject,
  fetchStatsForMode,
  formatAlreadyPercent,
  formatNumber,
  getStatsDerived,
  toNumber
} from "../../../../lib/newsPageUtils";
import PlotlyChart from "../../../../components/PlotlyChart";
import { DataModeControls, EmptyState, StatCard } from "../../../../components/news/NewsDashboardPrimitives";

export async function render(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const lensViews = asObject(derived.lens_views);
  const lensNames = asArray(lensViews.lens_names);
  const sourceRows = asArray(lensViews.source_rows);
  const summary = asObject(lensViews.summary);
  const topRows = sourceRows.slice(0, 20);
  const lensAverageRows = asArray(summary.source_lens_average_rows)
    .map((row) => ({
      lens: String(row?.lens || ""),
      mean: toNumber(row?.mean)
    }))
    .filter((row) => row.lens && row.mean !== null)
    .sort((a, b) => (b.mean || 0) - (a.mean || 0));
  const focusLens = lensAverageRows[0]?.lens || lensNames[0] || null;
  const matrix = topRows.map((row) => {
    const means = asObject(row.lens_means);
    return lensNames.map((lens) => toNumber(means[lens]) || 0);
  });

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Lens Matrix Summary</h3>
        <div className="stats-grid">
          <StatCard label="Coverage Mode" value={lensViews.coverage_mode || "n/a"} />
          <StatCard label="Sources" value={formatNumber(summary.source_count || sourceRows.length)} />
          <StatCard label="Lenses" value={formatNumber(lensNames.length)} />
          <StatCard label="Covered Articles" value={formatNumber(summary.covered_articles)} />
        </div>
      </div>

      <div className="panel">
        <h3>Lens Matrix Visuals</h3>
        {topRows.length === 0 || lensNames.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "heatmap",
                  x: lensNames,
                  y: topRows.map((row) => String(row.source || "Unknown")),
                  z: matrix,
                  colorscale: "Viridis"
                }
              ]}
              layout={{ title: "Source x Lens Mean Heatmap (Percent Scale)" }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: topRows.map((row) => String(row.source || "Unknown")),
                  y: topRows.map((row) => {
                    const means = asObject(row.lens_means);
                    return focusLens ? toNumber(means[focusLens]) || 0 : 0;
                  }),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{
                title: `Source Means for Focus Lens: ${focusLens || "n/a"}`,
                yaxis: { title: "Percent" }
              }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Top Sources x Lenses</h3>
        {topRows.length === 0 || lensNames.length === 0 ? (
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
                {topRows.map((row) => {
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
