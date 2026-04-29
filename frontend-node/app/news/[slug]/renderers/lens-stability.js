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
  const latentStability = asObject(derived.latent_space_stability);
  const stabilityRows = asArray(lensViews.stability_rows);
  const summary = asObject(lensViews.summary);
  const latentSummary = asObject(latentStability.summary);
  const latentComponentRows = asArray(latentStability.components);
  const loadingStabilityRows = asArray(latentStability.loading_stability).slice(0, 20);
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
          <StatCard label="Stable PCA Components" value={`${formatNumber(latentSummary.stable_component_count)} / ${formatNumber(latentSummary.component_count)}`} />
          <StatCard label="Mean Component Similarity" value={formatDecimal(latentSummary.mean_component_similarity, 3)} />
          <StatCard label="Most Unstable Loading" value={latentSummary.most_unstable_lens || "n/a"} />
          <StatCard label="Max Loading Std Dev" value={formatDecimal(latentSummary.max_loading_stddev, 4)} />
        </div>
      </div>

      <div className="panel">
        <h3>Latent Space Stability</h3>
        <StatusBlock status={String(latentStability.status || "unavailable")} reason={String(latentStability.reason || "")} />
        <p className="muted">
          Recomputes PCA across deterministic subsamples and compares component directions back to the full-corpus PCA. Low
          similarity or high loading variance means the latent axis should be interpreted cautiously.
        </p>
        {latentComponentRows.length === 0 && loadingStabilityRows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: latentComponentRows.map((row) => String(row.component || "Component")),
                  y: latentComponentRows.map((row) => toNumber(row.mean_cosine_similarity) || 0),
                  marker: { color: latentComponentRows.map((row) => (row.stable ? "#4fd1c5" : "#fd7e14")) }
                }
              ]}
              layout={{
                title: "PCA Component Direction Stability",
                yaxis: { title: "Mean cosine similarity", range: [0, 1] }
              }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  orientation: "h",
                  y: loadingStabilityRows.map((row) => String(row.lens || "Unknown")).reverse(),
                  x: loadingStabilityRows.map((row) => toNumber(row.max_loading_stddev) || 0).reverse(),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Most Variable PCA Lens Loadings", xaxis: { title: "Max loading std dev" } }}
            />
          </div>
        )}
        {latentComponentRows.length > 0 ? (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Component</th>
                <th>Stable</th>
                <th>Resamples</th>
                <th>Mean Similarity</th>
                <th>Min Similarity</th>
                <th>Explained Mean</th>
                <th>Explained Std Dev</th>
              </tr>
            </thead>
            <tbody>
              {latentComponentRows.map((row) => (
                <tr key={String(row.component || "component")}>
                  <td>{row.component || "Component"}</td>
                  <td>{row.stable ? "yes" : "no"}</td>
                  <td>{formatNumber(row.resamples)}</td>
                  <td>{formatDecimal(row.mean_cosine_similarity, 3)}</td>
                  <td>{formatDecimal(row.min_cosine_similarity, 3)}</td>
                  <td>{formatPercent(row.explained_variance_mean)}</td>
                  <td>{formatPercent(row.explained_variance_stddev)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
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
