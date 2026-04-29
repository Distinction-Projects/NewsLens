import {
  asArray,
  asObject,
  fetchStatsForMode,
  formatDecimal,
  formatNumber,
  formatPercent,
  getStatsDerived,
  toNumber
} from "../../../../lib/newsPageUtils";
import PlotlyChart from "../../../../components/PlotlyChart";
import { DataModeControls, EmptyState, StatCard, StatusBlock } from "../../../../components/news/NewsDashboardPrimitives";

export async function render(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const pca = asObject(derived.lens_pca);
  const mds = asObject(derived.lens_mds);
  const lensSeparation = asObject(derived.lens_separation);
  const explained = asArray(pca.explained_variance);
  const drivers = asArray(pca.variance_drivers);
  const centroids = asArray(pca.source_centroids);
  const silhouetteRows = asArray(lensSeparation.silhouette_like_by_source);
  const explainedRows = explained
    .map((row) => ({
      component: String(row?.component || ""),
      explained: toNumber(row?.explained_variance_ratio),
      cumulative: toNumber(row?.cumulative_variance_ratio)
    }))
    .filter((row) => row.component && row.explained !== null && row.cumulative !== null);
  const centroidRows = centroids
    .map((row) => ({
      source: String(row?.source || "Unknown"),
      count: toNumber(row?.count) || 0,
      pc1: toNumber(row?.pc1),
      pc2: toNumber(row?.pc2)
    }))
    .filter((row) => row.pc1 !== null && row.pc2 !== null);
  const pcaArticleRows = asArray(pca.article_points)
    .map((row) => ({
      title: String(row?.title || "Untitled"),
      source: String(row?.source || "Unknown"),
      strongestLens: String(row?.strongest_lens || "Unknown"),
      publishedAt: String(row?.published_at || "Unknown"),
      pc1: toNumber(row?.pc1),
      pc2: toNumber(row?.pc2)
    }))
    .filter((row) => row.pc1 !== null && row.pc2 !== null);
  const mdsArticleRows = asArray(mds.article_points)
    .map((row) => ({
      title: String(row?.title || "Untitled"),
      source: String(row?.source || "Unknown"),
      strongestLens: String(row?.strongest_lens || "Unknown"),
      publishedAt: String(row?.published_at || "Unknown"),
      mds1: toNumber(row?.mds1),
      mds2: toNumber(row?.mds2)
    }))
    .filter((row) => row.mds1 !== null && row.mds2 !== null);
  const mdsCentroidRows = asArray(mds.source_centroids)
    .map((row) => ({
      source: String(row?.source || "Unknown"),
      mds1: toNumber(row?.mds1),
      mds2: toNumber(row?.mds2)
    }))
    .filter((row) => row.mds1 !== null && row.mds2 !== null);
  const mdsStress = toNumber(mds.stress);
  const groupBySource = (rows) => {
    const grouped = new Map();
    for (const row of rows) {
      const source = String(row?.source || "Unknown");
      if (!grouped.has(source)) {
        grouped.set(source, []);
      }
      grouped.get(source).push(row);
    }
    return Array.from(grouped.entries()).sort((a, b) => {
      const sizeDelta = b[1].length - a[1].length;
      if (sizeDelta !== 0) {
        return sizeDelta;
      }
      return String(a[0]).localeCompare(String(b[0]));
    });
  };
  const pcaGroupedRows = groupBySource(pcaArticleRows);
  const mdsGroupedRows = groupBySource(mdsArticleRows);

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Latent Space Status</h3>
        <StatusBlock status={String(pca.status || "unavailable")} reason={String(pca.reason || "")} />
        <div className="stats-grid">
          <StatCard label="Articles" value={formatNumber(pca.n_articles)} />
          <StatCard label="Lenses" value={formatNumber(pca.n_lenses)} />
          <StatCard label="Components" value={formatNumber(asArray(pca.components).length)} />
          <StatCard label="Coverage Mode" value={pca.coverage_mode || "n/a"} />
          <StatCard label="MDS Stress" value={mdsStress !== null ? formatDecimal(mdsStress, 3) : "n/a"} />
          <StatCard label="Source Separation" value={formatDecimal(lensSeparation.separation_ratio, 3)} />
          <StatCard label="Silhouette-Like Mean" value={formatDecimal(lensSeparation.silhouette_like_mean, 3)} />
          <StatCard label="Separation Basis" value={lensSeparation.basis || "n/a"} />
        </div>
      </div>

      <div className="panel">
        <h3>PCA Visuals</h3>
        {explainedRows.length === 0 &&
        centroidRows.length === 0 &&
        pcaArticleRows.length === 0 &&
        mdsArticleRows.length === 0 ? (
          <EmptyState />
        ) : (
          <div>
            <div style={{ marginBottom: "12px" }}>
              <PlotlyChart
                data={[
                  {
                    type: "bar",
                    x: explainedRows.map((row) => row.component),
                    y: explainedRows.map((row) => (row.explained || 0) * 100),
                    name: "Explained %",
                    marker: { color: "#4fd1c5" }
                  },
                  {
                    type: "scatter",
                    mode: "lines+markers",
                    x: explainedRows.map((row) => row.component),
                    y: explainedRows.map((row) => (row.cumulative || 0) * 100),
                    name: "Cumulative %",
                    line: { color: "#7aa7ff" }
                  }
                ]}
                layout={{ title: "Explained Variance by Component", yaxis: { title: "Percent" } }}
              />
            </div>
            <div style={{ marginBottom: "12px" }}>
              <PlotlyChart
                data={[
                  ...pcaGroupedRows.map(([source, rows]) => ({
                    type: "scatter",
                    mode: "markers",
                    name: source,
                    x: rows.map((row) => row.pc1),
                    y: rows.map((row) => row.pc2),
                    text: rows.map((row) => row.title),
                    customdata: rows.map((row) => [row.source, row.strongestLens, row.publishedAt]),
                    hovertemplate:
                      "Title: %{text}<br>" +
                      "PC1: %{x:.3f}<br>" +
                      "PC2: %{y:.3f}<br>" +
                      "Source: %{customdata[0]}<br>" +
                      "Strongest Lens: %{customdata[1]}<br>" +
                      "Published: %{customdata[2]}<extra></extra>",
                    marker: { size: 8, opacity: 0.75 }
                  })),
                  ...(centroidRows.length > 0
                    ? [
                        {
                          type: "scatter",
                          mode: "markers+text",
                          name: "Source Centroids",
                          x: centroidRows.map((row) => row.pc1),
                          y: centroidRows.map((row) => row.pc2),
                          text: centroidRows.map((row) => row.source),
                          textposition: "top center",
                          hovertemplate: "Source: %{text}<br>PC1: %{x:.3f}<br>PC2: %{y:.3f}<extra></extra>",
                          marker: { symbol: "x", size: 12, color: "#111111" }
                        }
                      ]
                    : [])
                ]}
                layout={{ title: "Article Distribution in PC1/PC2 Space", xaxis: { title: "PC1" }, yaxis: { title: "PC2" } }}
              />
            </div>
            <div>
              <PlotlyChart
                data={[
                  ...mdsGroupedRows.map(([source, rows]) => ({
                    type: "scatter",
                    mode: "markers",
                    name: source,
                    x: rows.map((row) => row.mds1),
                    y: rows.map((row) => row.mds2),
                    text: rows.map((row) => row.title),
                    customdata: rows.map((row) => [row.source, row.strongestLens, row.publishedAt]),
                    hovertemplate:
                      "Title: %{text}<br>" +
                      "MDS1: %{x:.3f}<br>" +
                      "MDS2: %{y:.3f}<br>" +
                      "Source: %{customdata[0]}<br>" +
                      "Strongest Lens: %{customdata[1]}<br>" +
                      "Published: %{customdata[2]}<extra></extra>",
                    marker: { size: 8, opacity: 0.75 }
                  })),
                  ...(mdsCentroidRows.length > 0
                    ? [
                        {
                          type: "scatter",
                          mode: "markers+text",
                          name: "Source Centroids",
                          x: mdsCentroidRows.map((row) => row.mds1),
                          y: mdsCentroidRows.map((row) => row.mds2),
                          text: mdsCentroidRows.map((row) => row.source),
                          textposition: "top center",
                          hovertemplate: "Source: %{text}<br>MDS1: %{x:.3f}<br>MDS2: %{y:.3f}<extra></extra>",
                          marker: { symbol: "x", size: 12, color: "#111111" }
                        }
                      ]
                    : [])
                ]}
                layout={{
                  title: `Article Distribution in MDS1/MDS2 Space${mdsStress !== null ? ` (Stress: ${mdsStress.toFixed(3)})` : ""}`,
                  xaxis: { title: "MDS1" },
                  yaxis: { title: "MDS2" }
                }}
              />
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Explained Variance</h3>
        {explained.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Component</th>
                <th>Eigenvalue</th>
                <th>Explained</th>
                <th>Cumulative</th>
              </tr>
            </thead>
            <tbody>
              {explained.map((row) => (
                <tr key={String(row.component)}>
                  <td>{row.component}</td>
                  <td>{formatDecimal(row.eigenvalue, 4)}</td>
                  <td>{formatPercent(row.explained_variance_ratio)}</td>
                  <td>{formatPercent(row.cumulative_variance_ratio)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Variance Drivers</h3>
        {drivers.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Lens</th>
                <th>Weighted Contribution</th>
                <th>PC1</th>
                <th>PC2</th>
              </tr>
            </thead>
            <tbody>
              {drivers.slice(0, 20).map((row) => (
                <tr key={String(row.lens)}>
                  <td>{row.lens}</td>
                  <td>{formatDecimal(row.weighted_contribution, 4)}</td>
                  <td>{formatDecimal(row.pc1_loading, 4)}</td>
                  <td>{formatDecimal(row.pc2_loading, 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Source Centroids</h3>
        {centroids.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Source</th>
                <th>Count</th>
                <th>PC1</th>
                <th>PC2</th>
              </tr>
            </thead>
            <tbody>
              {centroids.slice(0, 25).map((row) => (
                <tr key={String(row.source || "unknown")}>
                  <td>{row.source || "Unknown"}</td>
                  <td>{formatNumber(row.count)}</td>
                  <td>{formatDecimal(row.pc1, 3)}</td>
                  <td>{formatDecimal(row.pc2, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Source Separation Diagnostics</h3>
        <StatusBlock status={String(lensSeparation.status || "unavailable")} reason={String(lensSeparation.reason || "")} />
        {silhouetteRows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: silhouetteRows.map((row) => String(row.source || "Unknown")),
                  y: silhouetteRows.map((row) => toNumber(row.silhouette_like_mean) || 0),
                  marker: { color: "#fd7e14" }
                }
              ]}
              layout={{ title: "Silhouette-Like Separation by Source", yaxis: { title: "Mean" } }}
            />
            <table className="news-table compact">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Articles</th>
                  <th>Silhouette-Like Mean</th>
                </tr>
              </thead>
              <tbody>
                {silhouetteRows.map((row) => (
                  <tr key={String(row.source || "unknown")}>
                    <td>{row.source || "Unknown"}</td>
                    <td>{formatNumber(row.count)}</td>
                    <td>{formatDecimal(row.silhouette_like_mean, 3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
