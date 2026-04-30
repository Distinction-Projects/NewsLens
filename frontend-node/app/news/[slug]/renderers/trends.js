import {
  asArray,
  asObject,
  fetchStatsForMode,
  formatDecimal,
  formatNumber,
  getStatsDerived,
  toNumber
} from "../../../../lib/newsPageUtils";
import PlotlyChart from "../../../../components/PlotlyChart";
import { DataModeControls, EmptyState, MiniBar, SectionHeader, StatCard, StatusBlock } from "../../../../components/news/NewsDashboardPrimitives";

function safePointRows(rows, xKey, yKey) {
  return asArray(rows)
    .map((row) => ({
      date: String(row?.date || ""),
      count: toNumber(row?.count) || 0,
      x: toNumber(row?.[xKey]),
      y: toNumber(row?.[yKey])
    }))
    .filter((row) => row.date && row.x !== null && row.y !== null);
}

function tagMomentumSeries(rows, topTags) {
  const selectedTags = new Set(topTags.map((row) => String(row?.tag || "")).filter(Boolean));
  const byTag = new Map();
  for (const row of asArray(rows)) {
    const tag = String(row?.tag || "");
    const date = String(row?.date || "");
    if (!selectedTags.has(tag) || !date) {
      continue;
    }
    if (!byTag.has(tag)) {
      byTag.set(tag, []);
    }
    byTag.get(tag).push({ date, count: toNumber(row?.count) || 0 });
  }
  return topTags
    .map((tagRow) => {
      const tag = String(tagRow?.tag || "");
      const points = byTag.get(tag) || [];
      points.sort((a, b) => a.date.localeCompare(b.date));
      return { tag, points };
    })
    .filter((series) => series.tag && series.points.length > 0);
}

export async function render(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const chartAggregates = asObject(derived.chart_aggregates);
  const dailyCounts = asArray(derived.daily_counts_utc);
  const hourCounts = asArray(chartAggregates.publish_hour_counts_utc);
  const lensTimeSeries = asObject(derived.lens_time_series);
  const temporalPca = asObject(derived.lens_temporal_embedding);
  const temporalMds = asObject(derived.lens_temporal_embedding_mds);
  const driftDiagnostics = asObject(derived.drift_diagnostics);
  const tagMomentum = asObject(derived.tag_momentum);
  const tagMomentumRows = asArray(tagMomentum.rows).slice(0, 8);
  const tagMomentumSummary = asObject(tagMomentum.summary);
  const tagMomentumDailySeries = tagMomentumSeries(tagMomentum.daily_tag_counts, tagMomentumRows.slice(0, 6));
  const lensSeriesRows = asArray(lensTimeSeries.series).slice(0, 8);
  const temporalPcaRows = safePointRows(temporalPca.day_centroids, "pc1", "pc2");
  const temporalMdsRows = safePointRows(temporalMds.day_centroids, "mds1", "mds2");
  const lensTimeSummary = asObject(lensTimeSeries.summary);
  const temporalPcaSummary = asObject(temporalPca.summary);
  const driftSummary = asObject(driftDiagnostics.summary);
  const driftWindows = asObject(driftDiagnostics.windows);
  const baselineWindow = asObject(driftWindows.baseline);
  const recentWindow = asObject(driftWindows.recent);
  const driftLensRows = asArray(driftDiagnostics.lens_drift).slice(0, 12);
  const sourceDrift = asObject(driftDiagnostics.source_distribution_drift);
  const tagDrift = asObject(driftDiagnostics.tag_distribution_drift);
  const sourceDriftRows = asArray(sourceDrift.rows).slice(0, 12);
  const tagDriftRows = asArray(tagDrift.rows).slice(0, 12);
  const maxDailyCount = dailyCounts.reduce((max, row) => Math.max(max, toNumber(row.count) || 0), 0);
  const maxHourCount = hourCounts.reduce((max, row) => Math.max(max, toNumber(row.count) || 0), 0);
  const firstDate = dailyCounts[0]?.date || "n/a";
  const lastDate = dailyCounts[dailyCounts.length - 1]?.date || "n/a";

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <SectionHeader
          kicker="Coverage"
          title="Temporal Coverage"
          summary="Basic publication span and article-count coverage for the available news corpus."
        />
        <div className="stats-grid">
          <StatCard label="Days Covered" value={formatNumber(dailyCounts.length)} />
          <StatCard label="First Day" value={firstDate} />
          <StatCard label="Latest Day" value={lastDate} />
          <StatCard label="Articles" value={formatNumber(derived.total_articles)} />
        </div>
      </div>

      <div className="panel">
        <SectionHeader
          kicker="Tag Momentum"
          title="Tag Momentum Over Time"
          summary="Daily counts for the highest momentum tags, ranked with exponential decay and recent-vs-baseline lift."
        />
        <StatusBlock status={String(tagMomentum.status || "unavailable")} reason={String(tagMomentum.reason || "")} />
        <div className="stats-grid">
          <StatCard label="Reference Date" value={tagMomentumSummary.reference_date || "n/a"} />
          <StatCard label="Recent Articles" value={formatNumber(tagMomentumSummary.recent_articles)} />
          <StatCard label="Baseline Articles" value={formatNumber(tagMomentumSummary.baseline_articles)} />
          <StatCard label="New Tags" value={formatNumber(tagMomentumSummary.new_tag_count)} />
          <StatCard label="Accelerating Tags" value={formatNumber(tagMomentumSummary.accelerating_tag_count)} />
        </div>
        {tagMomentumDailySeries.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            <PlotlyChart
              data={tagMomentumDailySeries.map((series) => ({
                type: "scatter",
                mode: "lines+markers",
                name: series.tag,
                x: series.points.map((point) => point.date),
                y: series.points.map((point) => point.count),
                hovertemplate: "%{fullData.name}<br>Date: %{x}<br>Articles: %{y}<extra></extra>"
              }))}
              layout={{
                title: "Daily Counts for Top Momentum Tags",
                yaxis: { title: "Articles" },
                legend: { orientation: "h" }
              }}
            />
            <div className="table-scroll">
              <table className="news-table compact">
                <thead>
                  <tr>
                    <th>Tag</th>
                    <th>Trend</th>
                    <th>Momentum</th>
                    <th>Recent</th>
                    <th>Baseline</th>
                    <th>Latest Seen</th>
                  </tr>
                </thead>
                <tbody>
                  {tagMomentumRows.map((row) => (
                    <tr key={String(row.tag || "unknown-tag")}>
                      <td>{row.tag || "Unknown"}</td>
                      <td>{row.trend || "n/a"}</td>
                      <td>{formatDecimal(row.momentum_score, 2)}</td>
                      <td>{formatNumber(row.recent_count)}</td>
                      <td>{formatNumber(row.baseline_count)}</td>
                      <td>{row.latest_seen || "n/a"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      <div className="panel">
        <SectionHeader
          kicker="Lens Trends"
          title="Lens Score Time Series"
          summary="Daily lens trajectories for the leading score dimensions in the dataset."
        />
        <StatusBlock status={String(lensTimeSeries.status || "unavailable")} reason={String(lensTimeSeries.reason || "")} />
        <div className="stats-grid">
          <StatCard label="Series Basis" value={lensTimeSeries.basis || "n/a"} />
          <StatCard label="Days" value={formatNumber(lensTimeSummary.days)} />
          <StatCard label="Articles With Scores" value={formatNumber(lensTimeSummary.articles_with_time_and_lens_scores)} />
          <StatCard label="Lenses" value={formatNumber(asArray(lensTimeSeries.lenses).length)} />
        </div>
        {lensSeriesRows.length === 0 ? (
          <EmptyState />
        ) : (
          <PlotlyChart
            data={lensSeriesRows.map((series) => {
              const points = asArray(series.points);
              return {
                type: "scatter",
                mode: "lines+markers",
                name: String(series.lens || "Lens"),
                x: points.map((point) => String(point.date || "")),
                y: points.map((point) => toNumber(point.mean) || 0),
                customdata: points.map((point) => [
                  toNumber(point.median),
                  toNumber(point.min),
                  toNumber(point.max),
                  toNumber(point.count)
                ]),
                hovertemplate:
                  "%{fullData.name}<br>Date: %{x}<br>Mean: %{y:.1f}%<br>Median: %{customdata[0]:.1f}%<br>Range: %{customdata[1]:.1f}% to %{customdata[2]:.1f}%<br>Articles: %{customdata[3]:.0f}<extra></extra>"
              };
            })}
            layout={{
              title: "Daily Mean Lens Scores",
              yaxis: { title: "Mean Score (%)", range: [0, 100] },
              legend: { orientation: "h" }
            }}
          />
        )}
      </div>

      <div className="panel">
        <SectionHeader
          kicker="Embedding Paths"
          title="Temporal Latent Movement"
          summary="How daily article centroids move through PCA and MDS space over time."
        />
        <StatusBlock status={String(temporalPca.status || "unavailable")} reason={String(temporalPca.reason || "")} />
        <div className="stats-grid">
          <StatCard label="Temporal Basis" value={temporalPca.basis || "n/a"} />
          <StatCard label="Days" value={formatNumber(temporalPcaSummary.days)} />
          <StatCard label="Start" value={temporalPcaSummary.start_date || "n/a"} />
          <StatCard label="End" value={temporalPcaSummary.end_date || "n/a"} />
        </div>
        {temporalPcaRows.length === 0 && temporalMdsRows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "scatter",
                  mode: "lines+markers+text",
                  name: "Daily PCA centroid",
                  x: temporalPcaRows.map((row) => row.x),
                  y: temporalPcaRows.map((row) => row.y),
                  text: temporalPcaRows.map((row) => row.date),
                  textposition: "top center",
                  customdata: temporalPcaRows.map((row) => [row.date, row.count]),
                  hovertemplate: "Date: %{customdata[0]}<br>PC1: %{x:.3f}<br>PC2: %{y:.3f}<br>Articles: %{customdata[1]}<extra></extra>",
                  marker: { size: temporalPcaRows.map((row) => Math.max(7, Math.min(20, Math.sqrt(row.count || 1) * 2.5))), color: "#4fd1c5" },
                  line: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Daily PCA Centroid Path", xaxis: { title: "PC1" }, yaxis: { title: "PC2" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "scatter",
                  mode: "lines+markers+text",
                  name: "Daily MDS centroid",
                  x: temporalMdsRows.map((row) => row.x),
                  y: temporalMdsRows.map((row) => row.y),
                  text: temporalMdsRows.map((row) => row.date),
                  textposition: "top center",
                  customdata: temporalMdsRows.map((row) => [row.date, row.count]),
                  hovertemplate: "Date: %{customdata[0]}<br>MDS1: %{x:.3f}<br>MDS2: %{y:.3f}<br>Articles: %{customdata[1]}<extra></extra>",
                  marker: { size: temporalMdsRows.map((row) => Math.max(7, Math.min(20, Math.sqrt(row.count || 1) * 2.5))), color: "#7aa7ff" },
                  line: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Daily MDS Centroid Path", xaxis: { title: "MDS1" }, yaxis: { title: "MDS2" } }}
            />
          </div>
        )}
        {temporalPcaRows.length > 0 ? (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Date</th>
                <th>Articles</th>
                <th>PC1</th>
                <th>PC2</th>
              </tr>
            </thead>
            <tbody>
              {temporalPcaRows.map((row) => (
                <tr key={row.date}>
                  <td>{row.date}</td>
                  <td>{formatNumber(row.count)}</td>
                  <td>{formatDecimal(row.x, 3)}</td>
                  <td>{formatDecimal(row.y, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>

      <div className="panel">
        <SectionHeader
          kicker="Stability"
          title="Drift Diagnostics"
          summary="Compares early and recent windows to flag lens, source, tag, and volume shifts."
        />
        <StatusBlock status={String(driftDiagnostics.status || "unavailable")} reason={String(driftDiagnostics.reason || "")} />
        <div className="stats-grid">
          <StatCard label="Severity" value={driftSummary.severity || "n/a"} />
          <StatCard label="Drift Score" value={formatDecimal(driftSummary.drift_score, 3)} />
          <StatCard label="Max Lens Delta" value={formatDecimal(driftSummary.max_abs_lens_delta, 2)} />
          <StatCard label="Source TVD" value={formatDecimal(driftSummary.source_total_variation_distance, 3)} />
          <StatCard label="Tag TVD" value={formatDecimal(driftSummary.tag_total_variation_distance, 3)} />
          <StatCard
            label="Windows"
            value={`${baselineWindow.start_date || "n/a"} to ${baselineWindow.end_date || "n/a"} / ${recentWindow.start_date || "n/a"} to ${recentWindow.end_date || "n/a"}`}
          />
        </div>
        {driftLensRows.length === 0 && sourceDriftRows.length === 0 && tagDriftRows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  orientation: "h",
                  y: driftLensRows.map((row) => String(row.lens || "Unknown")).reverse(),
                  x: driftLensRows.map((row) => toNumber(row.delta) || 0).reverse(),
                  marker: { color: driftLensRows.map((row) => ((toNumber(row.delta) || 0) >= 0 ? "#4fd1c5" : "#fd7e14")).reverse() }
                }
              ]}
              layout={{ title: "Lens Mean Shift: Recent minus Baseline", xaxis: { title: "Score percentage points" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  name: "Source share delta",
                  x: sourceDriftRows.map((row) => String(row.source || "Unknown")),
                  y: sourceDriftRows.map((row) => (toNumber(row.share_delta) || 0) * 100),
                  marker: { color: "#7aa7ff" }
                },
                {
                  type: "bar",
                  name: "Tag share delta",
                  x: tagDriftRows.map((row) => String(row.tag || "Unknown")),
                  y: tagDriftRows.map((row) => (toNumber(row.share_delta) || 0) * 100),
                  marker: { color: "#9d7dff" }
                }
              ]}
              layout={{ title: "Distribution Share Shifts", yaxis: { title: "Recent minus baseline share, points" } }}
            />
          </div>
        )}
        {driftLensRows.length > 0 ? (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Lens</th>
                <th>Baseline Mean</th>
                <th>Recent Mean</th>
                <th>Delta</th>
                <th>Baseline N</th>
                <th>Recent N</th>
              </tr>
            </thead>
            <tbody>
              {driftLensRows.map((row) => (
                <tr key={String(row.lens || "unknown-lens")}>
                  <td>{row.lens || "Unknown"}</td>
                  <td>{formatDecimal(row.baseline_mean, 2)}</td>
                  <td>{formatDecimal(row.recent_mean, 2)}</td>
                  <td>{formatDecimal(row.delta, 2)}</td>
                  <td>{formatNumber(row.baseline_count)}</td>
                  <td>{formatNumber(row.recent_count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>

      <div className="panel">
        <SectionHeader
          kicker="Volume"
          title="Daily Article Counts"
          summary="Daily publication counts with a matching UTC hourly distribution view."
        />
        {dailyCounts.length > 0 ? (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "scatter",
                  mode: "lines+markers",
                  x: dailyCounts.map((row) => String(row.date || "")),
                  y: dailyCounts.map((row) => toNumber(row.count) || 0),
                  line: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Daily Articles (UTC)", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: hourCounts.map((row) => String(row.hour).padStart(2, "0")),
                  y: hourCounts.map((row) => toNumber(row.count) || 0),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Publish Hour Distribution (UTC)", xaxis: { title: "Hour" }, yaxis: { title: "Articles" } }}
            />
          </div>
        ) : null}
        {dailyCounts.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Date</th>
                <th>Articles</th>
                <th>Volume</th>
              </tr>
            </thead>
            <tbody>
              {dailyCounts.map((row) => (
                <tr key={String(row.date)}>
                  <td>{row.date}</td>
                  <td>{formatNumber(row.count)}</td>
                  <td>
                    <MiniBar value={row.count} max={maxDailyCount} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <SectionHeader
          kicker="Hourly Pattern"
          title="Publish Hours (UTC)"
          summary="UTC publication-time concentration by hour across the loaded dataset."
        />
        {hourCounts.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <tbody>
              {hourCounts.map((row) => (
                <tr key={String(row.hour)}>
                  <th>{String(row.hour).padStart(2, "0")}:00</th>
                  <td>{formatNumber(row.count)}</td>
                  <td>
                    <MiniBar value={row.count} max={maxHourCount} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
