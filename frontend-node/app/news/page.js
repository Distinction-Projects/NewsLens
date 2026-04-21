import Link from "next/link";
import { NEWS_PAGES } from "../../lib/newsPages";

export const dynamic = "force-dynamic";

export default function NewsIndexPage() {
  return (
    <>
      <div className="panel">
        <h2>Migration Status</h2>
        <p className="muted">
          `digest`, `stats`, and `sources` now read live data from FastAPI. Remaining pages are scaffolded and will
          be migrated progressively.
        </p>
      </div>

      <div className="panel">
        <h2>Start Here</h2>
        <ul>
          <li>
            <Link href="/news/digest">News Digest</Link>
          </li>
          <li>
            <Link href="/news/stats">News Stats</Link>
          </li>
          <li>
            <Link href="/news/sources">News Sources</Link>
          </li>
        </ul>
      </div>

      <div className="panel">
        <h2>All Routed Pages</h2>
        <p className="muted">All legacy `/news/*` routes now exist in this Next.js surface.</p>
        <ul>
          {NEWS_PAGES.map((page) => (
            <li key={page.slug}>
              <Link href={`/news/${page.slug}`}>{page.title}</Link>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}
