import Link from "next/link";

export default function HomePage() {
  const workspaces = [
    {
      href: "/evaluation",
      title: "Model Evaluation",
      description: "Compare sentiment model performance across corpora and inspect benchmark tradeoffs.",
      eyebrow: "Models"
    },
    {
      href: "/text",
      title: "Text Analysis",
      description: "Run focused sentiment checks on short passages without leaving the dashboard.",
      eyebrow: "Sandbox"
    },
    {
      href: "/about",
      title: "About",
      description: "Review the project method, data pipeline, and research boundaries.",
      eyebrow: "Method"
    },
    {
      href: "/research",
      title: "Poster and Paper",
      description: "Use a publication-ready outline for the poster, paper, figures, and claim boundaries.",
      eyebrow: "Writeup"
    },
    {
      href: "/news",
      title: "News Analytics",
      description: "Explore source, topic, lens, workflow, and reliability diagnostics.",
      eyebrow: "News"
    }
  ];

  return (
    <main className="home-page">
      <section className="home-hero">
        <p className="home-kicker">Public research surface</p>
        <h1>NewsLens Research Dashboard</h1>
        <p className="muted">
          Explore sentiment-model evaluation and AI-assisted news analysis through a public, read-only dashboard.
        </p>
        <div className="home-hero-actions">
          <Link href="/news" className="news-nav-link active-link">
            Open News Analytics
          </Link>
          <Link href="/evaluation" className="news-nav-link">
            View Model Evaluation
          </Link>
        </div>
      </section>

      <section className="home-grid">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Workspace Index</p>
              <h2>Core Workspaces</h2>
            </div>
            <p className="muted compact-copy">Four entry points, each optimized for a different kind of analysis.</p>
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
          <h2>Exploratory, auditable, and bounded</h2>
          <p>
            NewsLens is designed for exploratory analysis. It supports transparent comparisons of model behavior,
            source-level framing patterns, topic-controlled differences, and data quality signals without treating
            automated scores as final judgments.
          </p>
          <div className="focus-points">
            <div className="focus-point">
              <strong>Comparative</strong>
              <span>Track how outlets, lenses, tags, and events differ under shared measurement rules.</span>
            </div>
            <div className="focus-point">
              <strong>Transparent</strong>
              <span>Keep derived metrics visible so users can audit what supports each visual claim.</span>
            </div>
            <div className="focus-point">
              <strong>Controlled</strong>
              <span>Favor topic, tag, and same-event views over pooled summaries when interpretation matters.</span>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
