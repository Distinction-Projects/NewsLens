import Link from "next/link";
import { NEWS_PAGES } from "../../lib/newsPages";

export const dynamic = "force-dynamic";

export default function NewsIndexPage() {
  const livePages = NEWS_PAGES;
  const statsBackedPages = NEWS_PAGES.filter(
    (page) =>
      !["digest", "raw-json", "integration", "scraped"].includes(page.slug) &&
      page.slug !== "workflow-status"
  );
  const digestBackedPages = NEWS_PAGES.filter((page) =>
    ["digest", "scraped", "workflow-status", "integration"].includes(page.slug)
  );

  return (
    <>
      <div className="panel news-index-hero">
        <p className="section-kicker">News Surface</p>
        <h2>Analytics entry point for source, lens, and workflow diagnostics</h2>
        <p className="muted">
          This section reads from the FastAPI news contract and exposes both exploratory analysis views and operational
          workflow checks.
        </p>
        <div className="stats-grid news-index-stats">
          <div className="stat-card">
            <small>Live Routes</small>
            <strong>{livePages.length}</strong>
          </div>
          <div className="stat-card">
            <small>Stats-Backed Views</small>
            <strong>{statsBackedPages.length}</strong>
          </div>
          <div className="stat-card">
            <small>Workflow Views</small>
            <strong>{digestBackedPages.length + 1}</strong>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Coverage</p>
            <h2>Implementation Status</h2>
          </div>
        </div>
        <p className="muted">
          {livePages.length} of {NEWS_PAGES.length} news pages are live in Next.js and read from the FastAPI contract.
        </p>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Navigation</p>
            <h2>Live News Pages</h2>
          </div>
          <p className="muted compact-copy">Use these as the primary entry points for the research surface.</p>
        </div>
        <div className="news-index-card-grid">
          {livePages.map((page) => (
            <Link key={page.slug} href={`/news/${page.slug}`} className="news-index-card">
              <strong>{page.title}</strong>
              <span>/news/{page.slug}</span>
            </Link>
          ))}
        </div>
      </div>

      <div className="panel">
        <p className="section-kicker">Contract Boundary</p>
        <h2>Route Coverage</h2>
        <p className="muted">
          All listed `/news/*` routes render live content from the FastAPI news contract.
        </p>
      </div>

      <div className="panel">
        <p className="section-kicker">System Flow</p>
        <h2>News Workflow Diagram</h2>
        <p className="muted">
          End-to-end flow from the upstream RSS contract to the Next.js `/news/*` pages.
        </p>

        <div className="workflow-diagram" role="img" aria-label="NewsLens workflow from RSS feed to news pages">
          <div className="workflow-row">
            <div className="workflow-box">
              <strong>1. RSS_Feeds (upstream)</strong>
              <p className="muted">
                JSON contract: current + snapshot files with article, score, and metadata payloads.
              </p>
            </div>
          </div>

          <div className="workflow-arrow" aria-hidden="true">
            v
          </div>

          <div className="workflow-row">
            <div className="workflow-box">
              <strong>2. Python service layer</strong>
              <p className="muted">
                `src/services/rss_digest.py` loads, normalizes, filters scrape failures, and computes derived analytics.
              </p>
            </div>
          </div>

          <div className="workflow-arrow" aria-hidden="true">
            v
          </div>

          <div className="workflow-row">
            <div className="workflow-box">
              <strong>3. FastAPI / Flask endpoints</strong>
              <p className="muted">
                `/api/news/digest`, `/api/news/stats`, `/api/news/upstream`, `/health/news-freshness`.
              </p>
            </div>
          </div>

          <div className="workflow-arrow" aria-hidden="true">
            v
          </div>

          <div className="workflow-split">
            <div className="workflow-lane">
              <div className="workflow-box">
                <strong>4A. Stats-backed pages</strong>
                <p className="muted">
                  Most analytical pages consume `/api/news/stats` `data.derived.*` fields.
                </p>
                <p className="muted">
                  Routes: {statsBackedPages.map((page) => `/news/${page.slug}`).join(", ")}
                </p>
              </div>
            </div>

            <div className="workflow-lane">
              <div className="workflow-box">
                <strong>4B. Digest/upstream workflow pages</strong>
                <p className="muted">
                  Operational pages consume digest/latest/upstream + freshness checks.
                </p>
                <p className="muted">
                  Routes: {digestBackedPages.map((page) => `/news/${page.slug}`).join(", ")} + `/news/raw-json`
                </p>
              </div>
            </div>
          </div>

          <div className="workflow-arrow" aria-hidden="true">
            v
          </div>

          <div className="workflow-row">
            <div className="workflow-box">
              <strong>5. Next.js News surface</strong>
              <p className="muted">
                `frontend-node/app/news/[slug]/page.js` renders live data for every route listed above.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
