import { notFound } from "next/navigation";
import { fetchNewsJson } from "../../../lib/newsApi";
import { getNewsPage, NEWS_PAGES } from "../../../lib/newsPages";
import PlotlyChart from "../../../components/PlotlyChart";

export const dynamic = "force-dynamic";

const MIGRATED_PAGE_SLUGS = new Set([
  "digest",
  "stats",
  "sources",
  "lenses",
  "lens-matrix",
  "lens-correlations",
  "lens-pca",
  "source-differentiation",
  "source-effects",
  "score-lab",
  "lens-explorer",
  "lens-by-source",
  "lens-stability",
  "tags",
  "source-tag-matrix",
  "trends",
  "scraped",
  "snapshot-compare",
  "data-quality",
  "workflow-status",
  "raw-json",
  "integration"
]);

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function asObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function toNumber(value) {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatNumber(value) {
  const number = toNumber(value);
  if (number === null) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-US").format(number);
}

function formatDecimal(value, digits = 2) {
  const number = toNumber(value);
  if (number === null) {
    return "n/a";
  }
  return number.toFixed(digits);
}

function formatPercent(value) {
  const number = toNumber(value);
  if (number === null) {
    return "n/a";
  }
  return `${(number * 100).toFixed(1)}%`;
}

function formatAlreadyPercent(value) {
  const number = toNumber(value);
  if (number === null) {
    return "n/a";
  }
  return `${number.toFixed(1)}%`;
}

function truncateText(value, maxLength = 220) {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  if (!text) {
    return "n/a";
  }
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

async function fetchStatsPayload(snapshotDate = null) {
  const query = typeof snapshotDate === "string" && snapshotDate ? `?snapshot_date=${encodeURIComponent(snapshotDate)}` : "";
  return fetchNewsJson(`/api/news/stats${query}`);
}

function getStatsDerived(payload) {
  return asObject(asObject(payload?.data).derived);
}

function snapshotDateFromSearchParams(searchParams) {
  const raw = typeof searchParams?.snapshot === "string" ? searchParams.snapshot.trim() : "";
  return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : null;
}

function PageIntro({ summary }) {
  return (
    <details className="news-page-intro">
      <summary>What this page does</summary>
      <p className="muted">{summary}</p>
    </details>
  );
}

function StatCard({ label, value, detail }) {
  return (
    <div className="stat-card">
      <span className="muted">{label}</span>
      <strong>{value}</strong>
      {detail ? <small className="muted">{detail}</small> : null}
    </div>
  );
}

function StatusPill({ children, tone = "neutral" }) {
  return <span className={`status-pill ${tone}`}>{children}</span>;
}

function EmptyState({ children = "No data available." }) {
  return <p className="muted">{children}</p>;
}

function StatusBlock({ status, reason }) {
  const tone = status === "ok" ? "good" : "bad";
  return (
    <p className="muted">
      <StatusPill tone={tone}>{status || "unknown"}</StatusPill>
      {reason ? ` ${reason}` : ""}
    </p>
  );
}

function MiniBar({ value, max }) {
  const number = toNumber(value) || 0;
  const limit = Math.max(toNumber(max) || 0, number, 1);
  const width = Math.max(0, Math.min(100, (number / limit) * 100));
  return (
    <div className="mini-bar" aria-label={`${formatNumber(number)} of ${formatNumber(limit)}`}>
      <span style={{ width: `${width}%` }} />
    </div>
  );
}

async function renderDigest() {
  const payload = await fetchNewsJson("/api/news/digest?limit=50");
  const rows = Array.isArray(payload?.data) ? payload.data : [];
  const sourceCounts = new Map();
  const avgBySource = new Map();
  for (const article of rows) {
    const source = String(article?.source_name || article?.source?.name || "Unknown");
    sourceCounts.set(source, (sourceCounts.get(source) || 0) + 1);
    const scorePercent = toNumber(article?.score?.percent);
    if (scorePercent !== null) {
      const bucket = avgBySource.get(source) || { total: 0, n: 0 };
      bucket.total += scorePercent;
      bucket.n += 1;
      avgBySource.set(source, bucket);
    }
  }
  const topSources = Array.from(sourceCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12);
  const avgSourceScores = topSources
    .map(([source]) => {
      const bucket = avgBySource.get(source);
      const average = bucket && bucket.n > 0 ? bucket.total / bucket.n : null;
      return { source, average };
    })
    .filter((row) => row.average !== null);

  return (
    <>
      <div className="panel">
        <h3>Digest Visuals</h3>
        {rows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: topSources.map((row) => row[0]),
                  y: topSources.map((row) => row[1]),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Top Sources in Current Digest Window", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: avgSourceScores.map((row) => row.source),
                  y: avgSourceScores.map((row) => row.average),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Average Score % by Source (Scored Rows)", yaxis: { title: "Score %" } }}
            />
          </div>
        )}
      </div>
      <div className="panel">
        <h3>Latest Articles ({rows.length})</h3>
        {rows.length === 0 ? (
          <p className="muted">No articles available.</p>
        ) : (
          <table className="news-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Source</th>
                <th>Title</th>
                <th>Tags</th>
                <th>Score %</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((article) => (
                <tr key={article.id || article.link}>
                  <td>{article.published_at || "n/a"}</td>
                  <td>{article.source_name || article?.source?.name || "Unknown"}</td>
                  <td>
                    <a href={article.link} target="_blank" rel="noreferrer">
                      {article.title || "Untitled"}
                    </a>
                  </td>
                  <td>{Array.isArray(article.tags) ? article.tags.join(", ") : "n/a"}</td>
                  <td>{typeof article?.score?.percent === "number" ? `${article.score.percent.toFixed(1)}%` : "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

async function renderStats() {
  const payload = await fetchNewsJson("/api/news/stats");
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

async function renderSources() {
  const payload = await fetchNewsJson("/api/news/stats");
  const derived = payload?.data?.derived || {};
  const sourceCounts = Array.isArray(derived?.source_counts) ? derived.source_counts : [];
  const scoredBySource = Array.isArray(derived?.chart_aggregates?.scored_by_source)
    ? derived.chart_aggregates.scored_by_source
    : [];

  const scoredLookup = new Map(
    scoredBySource
      .filter((row) => row && typeof row === "object")
      .map((row) => [String(row.source || ""), Number(row.count || 0)])
  );
  const chartRows = sourceCounts.slice(0, 20).map((row) => {
    const source = String(row.source || "Unknown");
    const count = Number(row.count || 0);
    const scored = scoredLookup.get(source) || 0;
    return {
      source,
      count,
      scored,
      coverage: count > 0 ? (scored / count) * 100 : 0
    };
  });

  return (
    <>
      <div className="panel">
        <h3>Source Charts</h3>
        {chartRows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: chartRows.map((row) => row.source),
                  y: chartRows.map((row) => row.count),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Article Volume by Source", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: chartRows.map((row) => row.source),
                  y: chartRows.map((row) => row.coverage),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Scoring Coverage by Source (%)", yaxis: { title: "Coverage %", range: [0, 100] } }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Source Coverage</h3>
        {sourceCounts.length === 0 ? (
          <p className="muted">No source data available.</p>
        ) : (
          <table className="news-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Articles</th>
                <th>Scored</th>
                <th>Coverage</th>
              </tr>
            </thead>
            <tbody>
              {sourceCounts.map((row) => {
                const source = String(row.source || "Unknown");
                const count = Number(row.count || 0);
                const scored = scoredLookup.get(source) || 0;
                const coverage = count > 0 ? scored / count : null;
                return (
                  <tr key={source}>
                    <td>{source}</td>
                    <td>{formatNumber(count)}</td>
                    <td>{formatNumber(scored)}</td>
                    <td>{coverage === null ? "n/a" : `${(coverage * 100).toFixed(1)}%`}</td>
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

async function renderLenses() {
  const payload = await fetchStatsPayload();
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

async function renderTags() {
  const payload = await fetchStatsPayload();
  const derived = getStatsDerived(payload);
  const chartAggregates = asObject(derived.chart_aggregates);
  const sourceTagViews = asObject(derived.source_tag_views);
  const tagCounts = asArray(derived.tag_counts).slice(0, 30);
  const tagDistribution = asArray(chartAggregates.tag_count_distribution);
  const sourceTagMatrixRows = asArray(chartAggregates.source_tag_matrix);
  const sourceLabels = asArray(sourceTagViews.source_labels).slice(0, 10);
  const tagLabels = asArray(sourceTagViews.tag_labels).slice(0, 12);
  const matrixLookup = new Map(
    sourceTagMatrixRows.map((row) => [pairKey(row.source, row.tag), toNumber(row.count) || 0])
  );
  const matrix = sourceLabels.map((source) => tagLabels.map((tag) => matrixLookup.get(pairKey(source, tag)) || 0));
  const maxTagCount = tagCounts.reduce((max, row) => Math.max(max, toNumber(row.count) || 0), 0);

  return (
    <>
      <div className="panel">
        <h3>Top Tags</h3>
        {tagCounts.length > 0 ? (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  orientation: "h",
                  y: tagCounts.map((row) => String(row.tag || "Unknown")).reverse(),
                  x: tagCounts.map((row) => toNumber(row.count) || 0).reverse(),
                  marker: { color: "#fd7e14" }
                }
              ]}
              layout={{ title: "Top Tags", xaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: tagDistribution.map((row) => String(row.label || "Unknown")),
                  y: tagDistribution.map((row) => toNumber(row.count) || 0),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Tags per Article Distribution", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "heatmap",
                  x: tagLabels,
                  y: sourceLabels,
                  z: matrix,
                  colorscale: "Viridis"
                }
              ]}
              layout={{ title: "Source x Tag Intensity" }}
            />
          </div>
        ) : null}
        {tagCounts.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table">
            <thead>
              <tr>
                <th>Tag</th>
                <th>Articles</th>
                <th>Relative Frequency</th>
              </tr>
            </thead>
            <tbody>
              {tagCounts.map((row) => (
                <tr key={String(row.tag || "unknown")}>
                  <td>{row.tag || "Unknown"}</td>
                  <td>{formatNumber(row.count)}</td>
                  <td>
                    <MiniBar value={row.count} max={maxTagCount} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Tags Per Article</h3>
        {tagDistribution.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Bucket</th>
                <th>Articles</th>
              </tr>
            </thead>
            <tbody>
              {tagDistribution.map((row) => (
                <tr key={String(row.label)}>
                  <td>{row.label}</td>
                  <td>{formatNumber(row.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

async function renderSourceTagMatrix() {
  const payload = await fetchStatsPayload();
  const derived = getStatsDerived(payload);
  const chartAggregates = asObject(derived.chart_aggregates);
  const sourceTagViews = asObject(derived.source_tag_views);
  const sourceLabels = asArray(sourceTagViews.source_labels).slice(0, 10);
  const tagLabels = asArray(sourceTagViews.tag_labels).slice(0, 10);
  const matrixRows = asArray(chartAggregates.source_tag_matrix);
  const sourceTotals = asArray(chartAggregates.source_tag_totals).slice(0, 12);
  const lookup = new Map(
    matrixRows.map((row) => [pairKey(row.source, row.tag), toNumber(row.count) || 0])
  );
  const matrix = sourceLabels.map((source) => tagLabels.map((tag) => lookup.get(pairKey(source, tag)) || 0));

  return (
    <>
      <div className="panel">
        <h3>Matrix Visuals</h3>
        {sourceLabels.length === 0 || tagLabels.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "heatmap",
                  x: tagLabels,
                  y: sourceLabels,
                  z: matrix,
                  colorscale: "Viridis"
                }
              ]}
              layout={{ title: "Source x Tag Intensity Heatmap" }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: sourceTotals.map((row) => String(row.source || "Unknown")),
                  y: sourceTotals.map((row) => toNumber(row.count) || 0),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Source Tag Totals", yaxis: { title: "Tag Assignments" } }}
            />
          </div>
        )}
      </div>
      <div className="panel">
        <h3>Source x Tag Matrix</h3>
        <p className="muted">Showing the top {formatNumber(sourceLabels.length)} sources and top {formatNumber(tagLabels.length)} tags.</p>
        {sourceLabels.length === 0 || tagLabels.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="table-scroll">
            <table className="news-table">
              <thead>
                <tr>
                  <th>Source</th>
                  {tagLabels.map((tag) => (
                    <th key={tag}>{tag}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sourceLabels.map((source) => (
                  <tr key={source}>
                    <td>{source}</td>
                    {tagLabels.map((tag) => (
                      <td key={`${source}-${tag}`}>{formatNumber(lookup.get(pairKey(source, tag)) || 0)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Source Tag Totals</h3>
        {sourceTotals.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Source</th>
                <th>Tag Assignments</th>
              </tr>
            </thead>
            <tbody>
              {sourceTotals.map((row) => (
                <tr key={String(row.source || "unknown")}>
                  <td>{row.source || "Unknown"}</td>
                  <td>{formatNumber(row.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

async function renderTrends() {
  const payload = await fetchStatsPayload();
  const derived = getStatsDerived(payload);
  const chartAggregates = asObject(derived.chart_aggregates);
  const dailyCounts = asArray(derived.daily_counts_utc);
  const hourCounts = asArray(chartAggregates.publish_hour_counts_utc);
  const maxDailyCount = dailyCounts.reduce((max, row) => Math.max(max, toNumber(row.count) || 0), 0);
  const maxHourCount = hourCounts.reduce((max, row) => Math.max(max, toNumber(row.count) || 0), 0);
  const firstDate = dailyCounts[0]?.date || "n/a";
  const lastDate = dailyCounts[dailyCounts.length - 1]?.date || "n/a";

  return (
    <>
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

async function renderDataQuality() {
  const payload = await fetchStatsPayload();
  const derived = getStatsDerived(payload);
  const dataQuality = asObject(derived.data_quality);
  const summary = asObject(dataQuality.summary);
  const scoreStatus = asObject(derived.score_status);
  const fieldCoverage = asArray(dataQuality.field_coverage);

  return (
    <>
      <div className="panel">
        <h3>Quality Snapshot</h3>
        <div className="stats-grid">
          <StatCard label="Included Articles" value={formatNumber(summary.total ?? derived.total_articles)} />
          <StatCard label="Input Articles" value={formatNumber(derived.input_articles)} />
          <StatCard label="Excluded Unscraped" value={formatNumber(derived.excluded_unscraped_articles)} />
          <StatCard label="Scored" value={formatNumber(summary.scored ?? derived.scored_articles)} />
          <StatCard label="Unscorable" value={formatNumber(scoreStatus.unscorable ?? derived.unscorable_articles)} />
          <StatCard label="Avg Tags / Article" value={formatDecimal(summary.average_tags, 2)} />
        </div>
      </div>

      <div className="panel">
        <h3>Field Coverage</h3>
        {fieldCoverage.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table">
            <thead>
              <tr>
                <th>Field</th>
                <th>Present</th>
                <th>Missing</th>
                <th>Coverage</th>
              </tr>
            </thead>
            <tbody>
              {fieldCoverage.map((row) => (
                <tr key={String(row.field)}>
                  <td>{row.field}</td>
                  <td>{formatNumber(row.present)}</td>
                  <td>{formatNumber(row.missing)}</td>
                  <td>
                    {formatAlreadyPercent(row.coverage_percent)}
                    <MiniBar value={row.coverage_percent} max={100} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Known Issue Counts</h3>
        <table className="news-table compact">
          <tbody>
            <tr>
              <th>Missing AI Summary</th>
              <td>{formatNumber(summary.missing_ai_summary)}</td>
            </tr>
            <tr>
              <th>Missing Published Date</th>
              <td>{formatNumber(summary.missing_published)}</td>
            </tr>
            <tr>
              <th>Missing Source</th>
              <td>{formatNumber(summary.missing_source)}</td>
            </tr>
            <tr>
              <th>Placeholder Zero Unscorable</th>
              <td>{formatNumber(scoreStatus.placeholder_zero_unscorable)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}

async function fetchEndpointStatus(label, path) {
  try {
    const payload = await fetchNewsJson(path);
    return {
      label,
      path,
      ok: true,
      status: payload?.status || "ok",
      detail: payload?.meta?.source_mode || payload?.data?.status || payload?.status || "reachable"
    };
  } catch (error) {
    return {
      label,
      path,
      ok: false,
      status: "error",
      detail: error instanceof Error ? error.message : String(error)
    };
  }
}

function EndpointTable({ rows }) {
  return (
    <table className="news-table">
      <thead>
        <tr>
          <th>Check</th>
          <th>Endpoint</th>
          <th>Status</th>
          <th>Detail</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.path}>
            <td>{row.label}</td>
            <td>
              <code>{row.path}</code>
            </td>
            <td>
              <StatusPill tone={row.ok ? "good" : "bad"}>{row.status}</StatusPill>
            </td>
            <td>{truncateText(row.detail)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

async function renderWorkflowStatus() {
  const rows = await Promise.all([
    fetchEndpointStatus("Digest", "/api/news/digest?limit=1"),
    fetchEndpointStatus("Latest", "/api/news/digest/latest"),
    fetchEndpointStatus("Stats", "/api/news/stats"),
    fetchEndpointStatus("Freshness", "/health/news-freshness")
  ]);
  const statsPayload = rows.find((row) => row.path === "/api/news/stats" && row.ok)
    ? await fetchStatsPayload()
    : null;
  const derived = getStatsDerived(statsPayload);

  return (
    <>
      <div className="panel">
        <h3>Pipeline Snapshot</h3>
        <div className="stats-grid">
          <StatCard label="Total Articles" value={formatNumber(derived.total_articles)} />
          <StatCard label="Scored Articles" value={formatNumber(derived.scored_articles)} />
          <StatCard label="Unscorable" value={formatNumber(derived.unscorable_articles)} />
          <StatCard label="Coverage" value={formatPercent(derived.score_coverage_ratio)} />
        </div>
      </div>

      <div className="panel">
        <h3>Runtime Checks</h3>
        <EndpointTable rows={rows} />
      </div>
    </>
  );
}

async function renderRawJson() {
  const payload = await fetchStatsPayload();
  const json = JSON.stringify(payload, null, 2);
  const maxLength = 20000;
  const preview = json.length > maxLength ? `${json.slice(0, maxLength)}\n... truncated ...` : json;

  return (
    <div className="panel">
      <h3>Stats Endpoint Preview</h3>
      <p className="muted">
        Showing <code>/api/news/stats</code>. Full endpoint switching will move over in a later interactive pass.
      </p>
      <pre className="json-preview">{preview}</pre>
    </div>
  );
}

async function renderIntegration() {
  const rows = await Promise.all([
    fetchEndpointStatus("API Health", "/health/news-freshness"),
    fetchEndpointStatus("Digest Contract", "/api/news/digest?limit=1"),
    fetchEndpointStatus("Latest Contract", "/api/news/digest/latest"),
    fetchEndpointStatus("Stats Contract", "/api/news/stats")
  ]);
  const healthy = rows.filter((row) => row.ok).length;

  return (
    <>
      <div className="panel">
        <h3>Integration Summary</h3>
        <div className="stats-grid">
          <StatCard label="Checks Passing" value={`${formatNumber(healthy)} / ${formatNumber(rows.length)}`} />
          <StatCard label="Runtime Surface" value="Next.js + FastAPI" />
          <StatCard label="Data Contract" value="RSS digest stats" />
        </div>
      </div>

      <div className="panel">
        <h3>Contract Checks</h3>
        <EndpointTable rows={rows} />
      </div>
    </>
  );
}

function getCorrelationPairRows(lenses, matrix) {
  const rows = [];
  for (let i = 0; i < lenses.length; i += 1) {
    for (let j = i + 1; j < lenses.length; j += 1) {
      const value = toNumber(asArray(matrix[i])[j]);
      if (value !== null) {
        rows.push({ lens_a: lenses[i], lens_b: lenses[j], value });
      }
    }
  }
  rows.sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
  return rows;
}

function sourceCountsToRows(sourceCountsValue) {
  if (Array.isArray(sourceCountsValue)) {
    return sourceCountsValue
      .map((row) => ({
        source: String(row?.source || "Unknown"),
        count: toNumber(row?.count) || 0
      }))
      .sort((a, b) => b.count - a.count || a.source.localeCompare(b.source));
  }
  const sourceCounts = asObject(sourceCountsValue);
  return Object.entries(sourceCounts)
    .map(([source, count]) => ({
      source: String(source || "Unknown"),
      count: toNumber(count) || 0
    }))
    .sort((a, b) => b.count - a.count || a.source.localeCompare(b.source));
}

async function renderLensMatrix() {
  const payload = await fetchStatsPayload();
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

async function renderLensCorrelations() {
  const payload = await fetchStatsPayload();
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

async function renderLensPca() {
  const payload = await fetchStatsPayload();
  const derived = getStatsDerived(payload);
  const pca = asObject(derived.lens_pca);
  const explained = asArray(pca.explained_variance);
  const drivers = asArray(pca.variance_drivers);
  const centroids = asArray(pca.source_centroids);
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

  return (
    <>
      <div className="panel">
        <h3>PCA Status</h3>
        <StatusBlock status={String(pca.status || "unavailable")} reason={String(pca.reason || "")} />
        <div className="stats-grid">
          <StatCard label="Articles" value={formatNumber(pca.n_articles)} />
          <StatCard label="Lenses" value={formatNumber(pca.n_lenses)} />
          <StatCard label="Components" value={formatNumber(asArray(pca.components).length)} />
          <StatCard label="Coverage Mode" value={pca.coverage_mode || "n/a"} />
        </div>
      </div>

      <div className="panel">
        <h3>PCA Visuals</h3>
        {explainedRows.length === 0 && centroidRows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
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
            <PlotlyChart
              data={[
                {
                  type: "scatter",
                  mode: "markers+text",
                  x: centroidRows.map((row) => row.pc1),
                  y: centroidRows.map((row) => row.pc2),
                  text: centroidRows.map((row) => row.source),
                  textposition: "top center",
                  marker: {
                    size: centroidRows.map((row) => Math.max(8, Math.min(28, 6 + Math.sqrt(row.count || 0) * 2))),
                    color: "#fd7e14",
                    opacity: 0.8
                  }
                }
              ]}
              layout={{ title: "Source Centroids in PC1/PC2 Space", xaxis: { title: "PC1" }, yaxis: { title: "PC2" } }}
            />
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
    </>
  );
}

function SourceDifferentiationBlock({ title, differentiation, confounded = false }) {
  const data = asObject(differentiation);
  const multivariate = asObject(data.multivariate);
  const classification = asObject(data.classification);
  const sourceCountRows = sourceCountsToRows(data.source_counts).slice(0, 20);
  const accuracy = toNumber(classification.accuracy);
  const baselineAccuracy = toNumber(classification.baseline_accuracy);
  const showAccuracyChart = accuracy !== null || baselineAccuracy !== null;
  return (
    <div className="panel">
      <h3>{title}</h3>
      {confounded ? <p className="muted">Label: topic-confounded</p> : null}
      <StatusBlock status={String(data.status || "unavailable")} reason={String(data.reason || "")} />
      <div className="stats-grid">
        <StatCard label="Articles" value={formatNumber(data.n_articles)} />
        <StatCard label="Sources" value={formatNumber(data.n_sources)} />
        <StatCard label="Lenses" value={formatNumber(data.n_lenses)} />
        <StatCard label="Permutations" value={formatNumber(data.permutations)} />
      </div>
      {sourceCountRows.length > 0 || showAccuracyChart ? (
        <div className="chart-grid">
          {sourceCountRows.length > 0 ? (
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: sourceCountRows.map((row) => row.source),
                  y: sourceCountRows.map((row) => row.count),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Source Counts in Analysis Slice", yaxis: { title: "Articles" } }}
            />
          ) : null}
          {showAccuracyChart ? (
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: ["Classifier", "Baseline"],
                  y: [accuracy !== null ? accuracy * 100 : 0, baselineAccuracy !== null ? baselineAccuracy * 100 : 0],
                  marker: { color: ["#7aa7ff", "#fd7e14"] }
                }
              ]}
              layout={{ title: "Classification Accuracy vs Baseline", yaxis: { title: "Accuracy %", range: [0, 100] } }}
            />
          ) : null}
        </div>
      ) : null}
      <table className="news-table compact">
        <tbody>
          <tr>
            <th>Multivariate F</th>
            <td>{formatDecimal(multivariate.f_stat, 4)}</td>
          </tr>
          <tr>
            <th>Multivariate R²</th>
            <td>{formatDecimal(multivariate.r_squared, 4)}</td>
          </tr>
          <tr>
            <th>Multivariate p_perm</th>
            <td>{formatDecimal(multivariate.p_perm, 4)}</td>
          </tr>
          <tr>
            <th>LOOCV Accuracy</th>
            <td>{formatPercent(classification.accuracy)}</td>
          </tr>
          <tr>
            <th>Baseline Accuracy</th>
            <td>{formatPercent(classification.baseline_accuracy)}</td>
          </tr>
          <tr>
            <th>Classification p_perm</th>
            <td>{formatDecimal(classification.p_perm, 4)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

async function renderSourceDifferentiation() {
  const payload = await fetchStatsPayload();
  const derived = getStatsDerived(payload);
  const pooled = asObject(derived.source_differentiation);
  const topicControl = asObject(derived.source_topic_control);
  const topics = asArray(topicControl.topics);

  return (
    <>
      <SourceDifferentiationBlock title="Pooled Source Differentiation" differentiation={pooled} confounded />
      <div className="panel">
        <h3>Within-Topic Source Differentiation</h3>
        {topics.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Topic</th>
                <th>Status</th>
                <th>Articles</th>
                <th>Sources</th>
                <th>F-stat</th>
                <th>LOOCV Acc</th>
              </tr>
            </thead>
            <tbody>
              {topics.map((topic) => {
                const diff = asObject(topic.source_differentiation);
                const multi = asObject(diff.multivariate);
                const cls = asObject(diff.classification);
                return (
                  <tr key={String(topic.topic || "unknown-topic")}>
                    <td>{topic.topic || "Unknown"}</td>
                    <td>{String(diff.status || "unavailable")}</td>
                    <td>{formatNumber(topic.n_articles)}</td>
                    <td>{formatNumber(topic.n_sources)}</td>
                    <td>{formatDecimal(multi.f_stat, 3)}</td>
                    <td>{formatPercent(cls.accuracy)}</td>
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

function SourceEffectsBlock({ title, effects, confounded = false }) {
  const data = asObject(effects);
  const rows = asArray(data.rows);
  const multipleTesting = asObject(data.multiple_testing);
  const etaRows = rows
    .map((row) => ({
      lens: String(row?.lens || ""),
      etaSq: toNumber(row?.eta_sq),
      sourceMeans: asObject(row?.source_means)
    }))
    .filter((row) => row.lens && row.etaSq !== null)
    .slice(0, 20);
  const focusLens = etaRows[0];
  const focusLensMeanRows = focusLens
    ? Object.entries(focusLens.sourceMeans)
        .map(([source, mean]) => ({
          source: String(source || "Unknown"),
          mean: toNumber(mean)
        }))
        .filter((row) => row.mean !== null)
        .sort((a, b) => (b.mean || 0) - (a.mean || 0))
    : [];
  return (
    <div className="panel">
      <h3>{title}</h3>
      {confounded ? <p className="muted">Label: topic-confounded</p> : null}
      <StatusBlock status={String(data.status || "unavailable")} reason={String(data.reason || "")} />
      <div className="stats-grid">
        <StatCard label="Rows" value={formatNumber(rows.length)} />
        <StatCard label="Permutations" value={formatNumber(data.permutations)} />
        <StatCard label="Multiple Testing" value={multipleTesting.method || "n/a"} />
        <StatCard label="Tests" value={formatNumber(multipleTesting.n_tests)} />
      </div>
      {etaRows.length > 0 ? (
        <div className="chart-grid">
          <PlotlyChart
            data={[
              {
                type: "bar",
                orientation: "h",
                y: etaRows.map((row) => row.lens).reverse(),
                x: etaRows.map((row) => row.etaSq || 0).reverse(),
                marker: { color: "#7aa7ff" }
              }
            ]}
            layout={{ title: "Lens Effect Size (eta squared)", xaxis: { title: "eta squared" } }}
          />
          <PlotlyChart
            data={[
              {
                type: "bar",
                x: focusLensMeanRows.map((row) => row.source),
                y: focusLensMeanRows.map((row) => row.mean || 0),
                marker: { color: "#fd7e14" }
              }
            ]}
            layout={{
              title: `Source Means for Top Lens: ${focusLens?.lens || "n/a"}`,
              yaxis: { title: "Mean Lens Percent" }
            }}
          />
        </div>
      ) : null}
      {rows.length === 0 ? (
        <EmptyState />
      ) : (
        <table className="news-table compact">
          <thead>
            <tr>
              <th>Lens</th>
              <th>F</th>
              <th>eta²</th>
              <th>p_perm_raw</th>
              <th>p_perm_fdr</th>
              <th>Source Gap</th>
              <th>Top / Bottom</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 30).map((row) => (
              <tr key={String(row.lens || "unknown-lens")}>
                <td>{row.lens || "Unknown"}</td>
                <td>{formatDecimal(row.f_stat, 3)}</td>
                <td>{formatDecimal(row.eta_sq, 3)}</td>
                <td>{formatDecimal(row.p_perm_raw, 4)}</td>
                <td>{formatDecimal(row.p_perm_fdr, 4)}</td>
                <td>{formatDecimal(row.source_gap, 2)}</td>
                <td>
                  {row.top_source || "n/a"} / {row.bottom_source || "n/a"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

async function renderSourceEffects() {
  const payload = await fetchStatsPayload();
  const derived = getStatsDerived(payload);
  const pooled = asObject(derived.source_lens_effects);
  const topicControl = asObject(derived.source_topic_control);
  const topics = asArray(topicControl.topics);

  return (
    <>
      <SourceEffectsBlock title="Pooled Source Effects" effects={pooled} confounded />
      <div className="panel">
        <h3>Within-Topic Source Effects</h3>
        {topics.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Topic</th>
                <th>Status</th>
                <th>Lens Rows</th>
                <th>Best Lens</th>
                <th>Best eta²</th>
              </tr>
            </thead>
            <tbody>
              {topics.map((topic) => {
                const effects = asObject(topic.source_lens_effects);
                const rows = asArray(effects.rows);
                const best = rows.length > 0 ? rows[0] : null;
                return (
                  <tr key={String(topic.topic || "unknown-topic")}>
                    <td>{topic.topic || "Unknown"}</td>
                    <td>{String(effects.status || "unavailable")}</td>
                    <td>{formatNumber(rows.length)}</td>
                    <td>{best?.lens || "n/a"}</td>
                    <td>{formatDecimal(best?.eta_sq, 3)}</td>
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

async function renderScoreLab() {
  const payload = await fetchStatsPayload();
  const derived = getStatsDerived(payload);
  const chartAggregates = asObject(derived.chart_aggregates);
  const scoreStatus = asObject(derived.score_status);
  const scoreStatusBySource = asArray(chartAggregates.score_status_by_source).slice(0, 20);
  const scoredBySource = asArray(chartAggregates.scored_by_source).slice(0, 20);
  const tagDistribution = asArray(chartAggregates.tag_count_distribution);
  const scoreStatusRows = scoreStatusBySource
    .map((row) => ({
      source: String(row?.source || "Unknown"),
      scored: toNumber(row?.scored) || 0,
      zero: toNumber(row?.zero_score) || 0,
      unscorable: toNumber(row?.unscorable) || 0
    }))
    .slice(0, 15);

  return (
    <>
      <div className="panel">
        <h3>Score Diagnostics</h3>
        <div className="stats-grid">
          <StatCard label="Scored Articles" value={formatNumber(derived.scored_articles)} />
          <StatCard label="Zero Scores" value={formatNumber(derived.zero_score_articles)} />
          <StatCard label="Unscorable" value={formatNumber(derived.unscorable_articles)} />
          <StatCard label="Missing Score Objects" value={formatNumber(derived.score_object_missing_articles)} />
          <StatCard label="Score Coverage" value={formatPercent(derived.score_coverage_ratio)} />
        </div>
      </div>

      <div className="panel">
        <h3>Score Lab Visuals</h3>
        {scoreStatusRows.length === 0 && scoredBySource.length === 0 && tagDistribution.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  name: "Scored",
                  x: scoreStatusRows.map((row) => row.source),
                  y: scoreStatusRows.map((row) => row.scored),
                  marker: { color: "#4fd1c5" }
                },
                {
                  type: "bar",
                  name: "Zero",
                  x: scoreStatusRows.map((row) => row.source),
                  y: scoreStatusRows.map((row) => row.zero),
                  marker: { color: "#fd7e14" }
                },
                {
                  type: "bar",
                  name: "Unscorable",
                  x: scoreStatusRows.map((row) => row.source),
                  y: scoreStatusRows.map((row) => row.unscorable),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Score Status by Source", barmode: "group", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: scoredBySource.map((row) => String(row?.source || "Unknown")),
                  y: scoredBySource.map((row) => toNumber(row?.count) || 0),
                  marker: { color: "#9d7dff" }
                }
              ]}
              layout={{ title: "Scored Articles by Source", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: tagDistribution.map((row) => String(row?.label || "Unknown")),
                  y: tagDistribution.map((row) => toNumber(row?.count) || 0),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Tag Count Distribution", yaxis: { title: "Articles" } }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Score Status by Source</h3>
        {scoreStatusBySource.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Source</th>
                <th>Scored</th>
                <th>Zero</th>
                <th>Unscorable</th>
              </tr>
            </thead>
            <tbody>
              {scoreStatusBySource.map((row) => (
                <tr key={String(row.source || "unknown")}>
                  <td>{row.source || "Unknown"}</td>
                  <td>{formatNumber(row.scored)}</td>
                  <td>{formatNumber(row.zero_score)}</td>
                  <td>{formatNumber(row.unscorable)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Scored Articles by Source</h3>
        {scoredBySource.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Source</th>
                <th>Count</th>
              </tr>
            </thead>
            <tbody>
              {scoredBySource.map((row) => (
                <tr key={String(row.source || "unknown")}>
                  <td>{row.source || "Unknown"}</td>
                  <td>{formatNumber(row.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Tag Count Distribution</h3>
        {tagDistribution.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Bucket</th>
                <th>Articles</th>
              </tr>
            </thead>
            <tbody>
              {tagDistribution.map((row) => (
                <tr key={String(row.label)}>
                  <td>{row.label}</td>
                  <td>{formatNumber(row.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="muted">
          Scored: {formatNumber(scoreStatus.scored)} | Positive: {formatNumber(scoreStatus.positive)} | Zero:{" "}
          {formatNumber(scoreStatus.zero)}
        </p>
      </div>
    </>
  );
}

async function renderLensExplorer() {
  const payload = await fetchStatsPayload();
  const derived = getStatsDerived(payload);
  const lensViews = asObject(derived.lens_views);
  const summary = asObject(lensViews.summary);
  const articleRows = asArray(lensViews.article_rows).slice(0, 40);
  const sourceRows = asArray(lensViews.source_rows).slice(0, 20);
  const dominantLensCounts = asArray(summary.dominant_lens_counts).slice(0, 12);
  const largestGapRows = articleRows
    .map((row) => ({
      title: truncateText(row?.title || "Untitled", 44),
      gap: toNumber(row?.gap_vs_runner_up)
    }))
    .filter((row) => row.gap !== null)
    .sort((a, b) => (b.gap || 0) - (a.gap || 0))
    .slice(0, 12);

  return (
    <>
      <div className="panel">
        <h3>Lens Explorer Summary</h3>
        <div className="stats-grid">
          <StatCard label="Coverage Mode" value={lensViews.coverage_mode || "n/a"} />
          <StatCard label="Articles with Lens Scores" value={formatNumber(summary.article_count)} />
          <StatCard label="Sources" value={formatNumber(summary.source_count)} />
          <StatCard label="Most Common Strongest Lens" value={summary.top_dominant_lens || "n/a"} />
        </div>
      </div>

      <div className="panel">
        <h3>Explorer Visuals</h3>
        {dominantLensCounts.length === 0 && largestGapRows.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: dominantLensCounts.map((row) => String(row?.lens || "Unknown")),
                  y: dominantLensCounts.map((row) => toNumber(row?.count) || 0),
                  marker: { color: "#4fd1c5" }
                }
              ]}
              layout={{ title: "Strongest Lens Frequency", yaxis: { title: "Articles" } }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  x: largestGapRows.map((row) => row.title),
                  y: largestGapRows.map((row) => row.gap || 0),
                  marker: { color: "#7aa7ff" }
                }
              ]}
              layout={{ title: "Largest Strongest-vs-Runner-Up Gaps", yaxis: { title: "Gap" } }}
            />
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Article Lens Rows</h3>
        {articleRows.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Title</th>
                <th>Source</th>
                <th>Strongest Lens</th>
                <th>Strongest %</th>
                <th>Gap vs Runner-up</th>
              </tr>
            </thead>
            <tbody>
              {articleRows.map((row, index) => (
                <tr key={`${String(row.title || "untitled")}-${index}`}>
                  <td>{truncateText(row.title || "Untitled", 90)}</td>
                  <td>{row.source || "Unknown"}</td>
                  <td>{row.strongest_lens || "n/a"}</td>
                  <td>{formatAlreadyPercent(row.strongest_percent)}</td>
                  <td>{formatDecimal(row.gap_vs_runner_up, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3>Source Lens Means</h3>
        {sourceRows.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table compact">
            <thead>
              <tr>
                <th>Source</th>
                <th>Articles</th>
                <th>Strongest Lens</th>
                <th>Strongest Gap</th>
              </tr>
            </thead>
            <tbody>
              {sourceRows.map((row) => (
                <tr key={String(row.source || "unknown")}>
                  <td>{row.source || "Unknown"}</td>
                  <td>{formatNumber(row.article_count)}</td>
                  <td>{row.strongest_lens || "n/a"}</td>
                  <td>{formatDecimal(row.strongest_gap, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

async function renderLensBySource() {
  const payload = await fetchStatsPayload();
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

async function renderLensStability() {
  const payload = await fetchStatsPayload();
  const derived = getStatsDerived(payload);
  const lensViews = asObject(derived.lens_views);
  const stabilityRows = asArray(lensViews.stability_rows);
  const summary = asObject(lensViews.summary);
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
      <div className="panel">
        <h3>Stability Summary</h3>
        <div className="stats-grid">
          <StatCard label="Lenses Analyzed" value={formatNumber(summary.stability_lens_count)} />
          <StatCard label="Avg Std Dev" value={formatDecimal(summary.stability_avg_stddev, 2)} />
          <StatCard label="Most Volatile Lens" value={summary.stability_top_lens || "n/a"} />
          <StatCard label="Total Samples" value={formatNumber(summary.stability_total_samples)} />
        </div>
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

async function renderScraped() {
  const payload = await fetchNewsJson("/api/news/digest?limit=100");
  const rows = asArray(payload?.data);
  const grouped = new Map();
  for (const row of rows) {
    const source = row?.source_name || asObject(row?.source).name || "Unknown";
    if (!grouped.has(source)) {
      grouped.set(source, []);
    }
    grouped.get(source).push(row);
  }
  const groups = Array.from(grouped.entries()).sort((a, b) => b[1].length - a[1].length);

  return (
    <>
      <div className="panel">
        <h3>Raw Scraped Digest</h3>
        <div className="stats-grid">
          <StatCard label="Records Loaded" value={formatNumber(rows.length)} />
          <StatCard label="Sources" value={formatNumber(groups.length)} />
          <StatCard
            label="With Scraped Payload"
            value={formatNumber(rows.filter((row) => asObject(row.scraped) && Object.keys(asObject(row.scraped)).length > 0).length)}
          />
        </div>
      </div>

      <div className="panel">
        <h3>Grouped by Source</h3>
        {groups.length === 0 ? (
          <EmptyState />
        ) : (
          <table className="news-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Articles</th>
                <th>Example Title</th>
              </tr>
            </thead>
            <tbody>
              {groups.slice(0, 25).map(([source, sourceRows]) => (
                <tr key={source}>
                  <td>{source}</td>
                  <td>{formatNumber(sourceRows.length)}</td>
                  <td>{truncateText(sourceRows[0]?.title || "Untitled", 120)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

function extractSnapshotMetrics(payload) {
  const derived = getStatsDerived(payload);
  const sourceCounts = asArray(derived.source_counts);
  const tagCounts = asArray(derived.tag_counts);
  const dailyCounts = asArray(derived.daily_counts_utc);
  return {
    total_articles: toNumber(derived.total_articles),
    scored_articles: toNumber(derived.scored_articles),
    zero_score_articles: toNumber(derived.zero_score_articles),
    unscorable_articles: toNumber(derived.unscorable_articles),
    score_coverage_ratio_percent:
      toNumber(derived.score_coverage_ratio) !== null ? (toNumber(derived.score_coverage_ratio) || 0) * 100 : null,
    source_count: sourceCounts.length,
    tag_count: tagCounts.length,
    days_covered: dailyCounts.length
  };
}

function metricDelta(current, snapshot) {
  if (current === null || snapshot === null) {
    return "n/a";
  }
  const delta = current - snapshot;
  return Number.isInteger(delta) ? `${delta >= 0 ? "+" : ""}${delta}` : `${delta >= 0 ? "+" : ""}${delta.toFixed(1)}`;
}

function pairKey(a, b) {
  return `${String(a || "")}\u0000${String(b || "")}`;
}

async function renderSnapshotCompare(searchParams) {
  const snapshotDate = snapshotDateFromSearchParams(searchParams);
  if (!snapshotDate) {
    return (
      <div className="panel">
        <h3>Snapshot Compare</h3>
        <p className="muted">Add a snapshot date in the query string to compare: <code>?snapshot=YYYY-MM-DD</code></p>
      </div>
    );
  }

  const [currentPayload, snapshotPayload] = await Promise.all([
    fetchStatsPayload(),
    fetchStatsPayload(snapshotDate)
  ]);
  const currentMetrics = extractSnapshotMetrics(currentPayload);
  const snapshotMetrics = extractSnapshotMetrics(snapshotPayload);
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

function renderPlaceholder(title) {
  return (
    <div className="panel">
      <h3>Migration In Progress</h3>
      <p className="muted">
        {title} is routed and ready, but the full interactive port is still pending. This page will be migrated in a
        later pass while keeping existing Dash behavior intact.
      </p>
    </div>
  );
}

async function renderPageBody(slug, title, searchParams) {
  if (slug === "digest") {
    return renderDigest();
  }
  if (slug === "stats") {
    return renderStats();
  }
  if (slug === "sources") {
    return renderSources();
  }
  if (slug === "lenses") {
    return renderLenses();
  }
  if (slug === "lens-matrix") {
    return renderLensMatrix();
  }
  if (slug === "lens-correlations") {
    return renderLensCorrelations();
  }
  if (slug === "lens-pca") {
    return renderLensPca();
  }
  if (slug === "source-differentiation") {
    return renderSourceDifferentiation();
  }
  if (slug === "source-effects") {
    return renderSourceEffects();
  }
  if (slug === "score-lab") {
    return renderScoreLab();
  }
  if (slug === "lens-explorer") {
    return renderLensExplorer();
  }
  if (slug === "lens-by-source") {
    return renderLensBySource();
  }
  if (slug === "lens-stability") {
    return renderLensStability();
  }
  if (slug === "tags") {
    return renderTags();
  }
  if (slug === "source-tag-matrix") {
    return renderSourceTagMatrix();
  }
  if (slug === "trends") {
    return renderTrends();
  }
  if (slug === "scraped") {
    return renderScraped();
  }
  if (slug === "snapshot-compare") {
    return renderSnapshotCompare(searchParams);
  }
  if (slug === "data-quality") {
    return renderDataQuality();
  }
  if (slug === "workflow-status") {
    return renderWorkflowStatus();
  }
  if (slug === "raw-json") {
    return renderRawJson();
  }
  if (slug === "integration") {
    return renderIntegration();
  }
  return renderPlaceholder(title);
}

export default async function NewsDetailPage({ params, searchParams }) {
  const page = getNewsPage(params.slug);
  if (!page) {
    notFound();
  }

  let body = null;
  let errorMessage = null;
  try {
    body = await renderPageBody(page.slug, page.title, searchParams);
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : String(error);
  }

  return (
    <>
      <div className="page-title-row">
        <h2>{page.title}</h2>
        <p className="muted">
          {MIGRATED_PAGE_SLUGS.has(page.slug) ? "Live FastAPI data" : "Routed placeholder for phased migration"}
        </p>
      </div>
      <PageIntro summary={page.summary} />

      {errorMessage ? (
        <div className="panel">
          <h3>API Error</h3>
          <p className="muted">{errorMessage}</p>
          <p>
            Ensure FastAPI is running: <code>uvicorn src.api.fastapi_app:app --reload --port 9000</code>
          </p>
        </div>
      ) : (
        body
      )}
    </>
  );
}
