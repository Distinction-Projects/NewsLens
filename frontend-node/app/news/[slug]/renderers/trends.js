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
import { DataModeControls, EmptyState, MiniBar, StatCard, StatusBlock } from "../../../../components/news/NewsDashboardPrimitives";

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

export async function render(searchParams) {
  const payload = await fetchStatsForMode(searchParams);
  const derived = getStatsDerived(payload);
  const chartAggregates = asObject(derived.chart_aggregates);
  const dailyCounts = asArray(derived.daily_counts_utc);
  const hourCounts = asArray(chartAggregates.publish_hour_counts_utc);
  const lensTimeSeries = asObject(derived.lens_time_series);
  const temporalPca = asObject(derived.lens_temporal_embedding);
  const temporalMds = asObject(derived.lens_temporal_embedding_mds);
  const lensSeriesRows = asArray(lensTimeSeries.series).slice(0, 8);
  const temporalPcaRows = safePointRows(temporalPca.day_centroids, "pc1", "pc2");
  const temporalMdsRows = safePointRows(temporalMds.day_centroids, "mds1", "mds2");
  const lensTimeSummary = asObject(lensTimeSeries.summary);
  const temporalPcaSummary = asObject(temporalPca.summary);
  const maxDailyCount = dailyCounts.reduce((max, row) => Math.max(max, toNumber(row.count) || 0), 0);
  const maxHourCount = hourCounts.reduce((max, row) => Math.max(max, toNumber(row.count) || 0), 0);
  const firstDate = dailyCounts[0]?.date || "n/a";
  const lastDate = dailyCounts[dailyCounts.length - 1]?.date || "n/a";

  return (
    <>
      <DataModeControls searchParams={searchParams} />
      <div className="panel">
        <h3>Temporal Coverage</h3>
        <div className="stats-grid">
          <StatCard label="Days Covered" value={formatNumber(dailyCounts.length)} />
          <StatCard label="First Day" value={firstDate} />
          <StatCard label="Latest Day" value={lastDate} />
          <StatCard label="Articles" value={formatNumber(derived.total_articles)} />
        </div>
      </div>

      <div className="panel">
        <h3>Lens Score Time Series</h3>
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
        <h3>Temporal Latent Movement</h3>
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
        <h3>Daily Article Counts</h3>
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
        <h3>Publish Hours (UTC)</h3>
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
