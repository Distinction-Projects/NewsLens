import { notFound } from "next/navigation";
import { fetchNewsJson } from "../../../lib/newsApi";
import { getNewsPage, NEWS_PAGES } from "../../../lib/newsPages";

export const dynamic = "force-dynamic";

const MIGRATED_PAGE_SLUGS = new Set([
  "digest",
  "stats",
  "sources",
  "lenses",
  "tags",
  "source-tag-matrix",
  "trends",
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

async function fetchStatsPayload() {
  return fetchNewsJson("/api/news/stats");
}

function getStatsDerived(payload) {
  return asObject(asObject(payload?.data).derived);
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

  return (
    <>
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

  return (
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
  const tagCounts = asArray(derived.tag_counts).slice(0, 30);
  const tagDistribution = asArray(chartAggregates.tag_count_distribution);
  const maxTagCount = tagCounts.reduce((max, row) => Math.max(max, toNumber(row.count) || 0), 0);

  return (
    <>
      <div className="panel">
        <h3>Top Tags</h3>
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
    matrixRows.map((row) => [`${String(row.source || "")}\u0000${String(row.tag || "")}`, toNumber(row.count) || 0])
  );

  return (
    <>
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
                      <td key={`${source}-${tag}`}>{formatNumber(lookup.get(`${source}\u0000${tag}`) || 0)}</td>
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

async function renderPageBody(slug, title) {
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
  if (slug === "tags") {
    return renderTags();
  }
  if (slug === "source-tag-matrix") {
    return renderSourceTagMatrix();
  }
  if (slug === "trends") {
    return renderTrends();
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

export default async function NewsDetailPage({ params }) {
  const page = getNewsPage(params.slug);
  if (!page) {
    notFound();
  }

  let body = null;
  let errorMessage = null;
  try {
    body = await renderPageBody(page.slug, page.title);
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
