"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { getNewsPage, NEWS_PAGE_GROUPS, newsPageLabel } from "../../lib/newsPages";

const QUICK_LINKS = ["digest", "tags", "group-latent-space", "trends", "sources"];

export default function NewsNavigation() {
  const pathname = usePathname();

  function pageLink(slug, closeMenu = false) {
    const page = getNewsPage(slug);
    const href = `/news/${slug}`;
    return (
      <Link
        key={slug}
        href={href}
        prefetch={false}
        aria-label={page.title}
        aria-current={pathname === href ? "page" : undefined}
        onClick={closeMenu ? (event) => event.currentTarget.closest("details").removeAttribute("open") : undefined}
      >
        {newsPageLabel(page)}
      </Link>
    );
  }

  return (
    <nav className="news-navigation" aria-label="News navigation">
      <div className="news-quick-links">
        <Link href="/news" aria-current={pathname === "/news" ? "page" : undefined}>
          All news
        </Link>
        {QUICK_LINKS.map((slug) => pageLink(slug))}
      </div>
      <details className="news-browse-menu" key={pathname}>
        <summary>All views</summary>
        <div className="news-browse-groups">
          {NEWS_PAGE_GROUPS.map((group) => (
            <section key={group.id} aria-label={group.title}>
              <h2>{group.title}</h2>
              {group.slugs.map((slug) => pageLink(slug, true))}
            </section>
          ))}
        </div>
      </details>
    </nav>
  );
}
