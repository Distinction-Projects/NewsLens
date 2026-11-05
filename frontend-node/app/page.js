import Link from "next/link";

export default function HomePage() {
  const workspaces = [
    {
      href: "/evaluation",
      title: "Model Evaluation",
      description: "Compare sentiment models across datasets.",
      eyebrow: "Models"
    },
    {
      href: "/text",
      title: "Text Analysis",
      description: "Try sentiment analysis on a passage of your own.",
      eyebrow: "Sandbox"
    },
    {
      href: "/about",
      title: "About",
      description: "Learn how the project works.",
      eyebrow: "Method"
    },
    {
      href: "/research",
      title: "Poster and Paper",
      description: "Read the research and explore the figures.",
      eyebrow: "Writeup"
    },
    {
      href: "/news",
      title: "News Analytics",
      description: "Browse articles and compare topics, sources, and lenses.",
      eyebrow: "News"
    }
  ];

  return (
    <main className="home-page">
      <section className="home-hero">
        <p className="home-kicker">NewsLens</p>
        <h1>A closer look at the news.</h1>
        <p className="muted">
          Explore articles, compare how sources cover a topic, and follow changes over time.
        </p>
        <div className="home-hero-actions">
          <Link href="/news/digest" className="news-nav-link active-link">
            Browse articles
          </Link>
          <Link href="/news" className="news-nav-link">
            Explore the views
          </Link>
        </div>
      </section>

      <section className="home-grid">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Explore</p>
              <h2>Choose where to start</h2>
            </div>
          </div>
          <div className="home-card-grid">
            {workspaces.map((workspace) => (
              <Link key={workspace.href} href={workspace.href} className="home-workspace-card">
                <span className="home-card-eyebrow">{workspace.eyebrow}</span>
                <strong>{workspace.title}</strong>
                <span>{workspace.description}</span>
              </Link>
            ))}
          </div>
        </div>

        <div className="panel home-focus-panel">
          <p className="section-kicker">Research Focus</p>
          <h2>One story, several lenses</h2>
          <p>
            Lenses ask different questions about an article: who has a voice, who is treated as an authority,
            or how emotion shapes the story. Use them to compare readings and return to the articles.
          </p>
          <div className="focus-points">
            <div className="focus-point">
              <strong>Choose a topic</strong>
              <span>Use tags to focus on the coverage you want to explore.</span>
            </div>
            <div className="focus-point">
              <strong>Compare sources</strong>
              <span>Look at differences within a topic or a shared event.</span>
            </div>
            <div className="focus-point">
              <strong>Read for yourself</strong>
              <span>Follow the annotations back to the articles.</span>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
