import Link from "next/link";
import { NEWS_PAGES } from "../../lib/newsPages";

export default function NewsLayout({ children }) {
  return (
    <main className="news-layout-page">
      <section className="panel news-layout-hero">
        <p className="section-kicker">News Analytics</p>
        <h1>FastAPI-backed source, lens, workflow, and event diagnostics</h1>
        <p className="muted">
          The news surface reads from the backend contract and exposes exploratory comparisons, data quality checks,
          workflow health, and same-event analysis.
        </p>
      </section>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Index</p>
            <h2>Pages</h2>
          </div>
          <p className="muted compact-copy">All routes below stay inside the same shared analytics surface.</p>
        </div>
        <nav className="news-layout-grid">
          {NEWS_PAGES.map((page) => (
            <Link key={page.slug} href={`/news/${page.slug}`} className="news-layout-card" aria-label={page.title}>
              <strong>{page.title}</strong>
              <span>{page.summary}</span>
            </Link>
          ))}
        </nav>
      </div>

      {children}
    </main>
  );
}
