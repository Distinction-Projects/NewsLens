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
    </>
  );
}
