import Link from "next/link";
import { NEWS_PAGES } from "../../lib/newsPages";

export const dynamic = "force-dynamic";

const LIVE_PAGE_SLUGS = new Set([
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

export default function NewsIndexPage() {
  const livePages = NEWS_PAGES.filter((page) => LIVE_PAGE_SLUGS.has(page.slug));
  const scaffoldedPages = NEWS_PAGES.filter((page) => !LIVE_PAGE_SLUGS.has(page.slug));
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
      <div className="panel">
        <h2>Migration Status</h2>
        <p className="muted">
          {livePages.length} news pages now read live data from FastAPI. The remaining routes stay scaffolded while
          the Dash interactions are ported progressively.
        </p>
      </div>

      <div className="panel">
        <h2>Live Node Pages</h2>
        <ul>
          {livePages.map((page) => (
            <li key={page.slug}>
              <Link href={`/news/${page.slug}`}>{page.title}</Link>
            </li>
          ))}
        </ul>
      </div>

      <div className="panel">
        <h2>Scaffolded Routes</h2>
        <p className="muted">These routes exist in Next.js and will be migrated in later passes.</p>
        <ul>
          {scaffoldedPages.map((page) => (
            <li key={page.slug}>
              <Link href={`/news/${page.slug}`}>{page.title}</Link>
            </li>
          ))}
        </ul>
      </div>

      <div className="panel">
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
            ↓
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
            ↓
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
            ↓
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
            ↓
          </div>

          <div className="workflow-row">
            <div className="workflow-box">
              <strong>5. Next.js News surface</strong>
              <p className="muted">
                `frontend-node/app/news/[slug]/page.js` renders live data where migrated; scaffolded routes remain
                linked for progressive porting.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
