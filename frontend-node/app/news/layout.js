import Link from "next/link";
import { NEWS_PAGES } from "../../lib/newsPages";

export default function NewsLayout({ children }) {
  return (
    <main>
      <h1>News</h1>
      <p className="muted">
        NewsLens analytics surface backed by the FastAPI contract.
      </p>

      <div className="panel">
        <h2>Pages</h2>
        <nav className="news-nav-grid">
          {NEWS_PAGES.map((page) => (
            <Link key={page.slug} href={`/news/${page.slug}`} className="news-nav-link">
              {page.title}
            </Link>
          ))}
        </nav>
      </div>

      {children}
    </main>
  );
}
