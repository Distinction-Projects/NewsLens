import { notFound } from "next/navigation";
import { fetchNewsJson, newsApiBaseUrl } from "../../../lib/newsApi";
import { getNewsPage, NEWS_PAGES } from "../../../lib/newsPages";

export const dynamic = "force-dynamic";

function formatNumber(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-US").format(value);
}

function formatPercent(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function PageIntro({ summary }) {
  return (
    <details className="news-page-intro">
      <summary>What this page does</summary>
      <p className="muted">{summary}</p>
    </details>
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
  return renderPlaceholder(title);
}

export function generateStaticParams() {
  return NEWS_PAGES.map((entry) => ({ slug: entry.slug }));
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
          API base: <code>{newsApiBaseUrl()}</code>
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
