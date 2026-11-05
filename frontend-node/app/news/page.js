import Link from "next/link";
import { getNewsPage, NEWS_PAGE_GROUPS, newsPageLabel } from "../../lib/newsPages";

export const dynamic = "force-dynamic";

const STARTING_POINTS = [
  { slug: "digest", title: "Read the articles", description: "Browse the collection by source, date, or tag." },
  { slug: "group-latent-space", title: "Explore topics and tags", description: "See how topics and sources relate across lenses." },
  { slug: "trends", title: "Follow changes over time", description: "Explore shifts in coverage, tags, and lens values." }
];

function PageGroup({ group }) {
  return (
    <section className="news-page-group" aria-labelledby={`group-${group.id}`}>
      <h2 id={`group-${group.id}`}>{group.title}</h2>
      <p className="muted">{group.summary}</p>
      <div className="news-index-card-grid">
        {group.slugs.map((slug) => {
          const page = getNewsPage(slug);
          return (
            <Link key={slug} href={`/news/${slug}`} className="news-index-card" prefetch={false}>
              <strong>{newsPageLabel(page)}</strong>
              <span>{page.summary}</span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

export default function NewsIndexPage() {
  return (
    <>
      <header className="news-index-heading">
        <p className="section-kicker">NewsLens</p>
        <h1>Explore the news</h1>
        <p className="muted">Read articles, compare coverage, and explore patterns through different lenses.</p>
      </header>

      <section className="news-start-grid" aria-label="Start exploring">
        {STARTING_POINTS.map((item, index) => (
          <Link key={item.slug} href={`/news/${item.slug}`} className="news-start-card" prefetch={false}>
            <span className="section-kicker">0{index + 1}</span>
            <h2>{item.title}</h2>
            <p className="muted">{item.description}</p>
            <span className="news-start-arrow" aria-hidden="true">&rarr;</span>
          </Link>
        ))}
      </section>

      {NEWS_PAGE_GROUPS.filter((group) => group.id !== "tools").map((group) => <PageGroup key={group.id} group={group} />)}

      <details className="news-diagnostics">
        <summary>Data and diagnostics</summary>
        <PageGroup group={NEWS_PAGE_GROUPS.find((group) => group.id === "tools")} />
      </details>
    </>
  );
}
