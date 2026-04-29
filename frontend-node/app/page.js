import Link from "next/link";

export default function HomePage() {
  const workspaces = [
    {
      href: "/evaluation",
      title: "Model Evaluation",
      description: "Compare sentiment model performance across corpora."
    },
    {
      href: "/text",
      title: "Text Analysis",
      description: "Run focused sentiment checks on short passages."
    },
    {
      href: "/about",
      title: "About",
      description: "Review the project method, data pipeline, and research boundaries."
    },
    {
      href: "/news",
      title: "News Analytics",
      description: "Explore source, topic, lens, workflow, and reliability diagnostics."
    }
  ];

  return (
    <main className="home-page">
      <section className="home-hero">
        <h1>NewsLens Research Dashboard</h1>
        <p className="muted">
          Explore sentiment-model evaluation and AI-assisted news analysis through a public, read-only dashboard.
        </p>
      </section>

      <section className="home-grid">
        <div className="panel">
          <h2>Core Workspaces</h2>
          <div className="home-card-grid">
            {workspaces.map((workspace) => (
              <Link key={workspace.href} href={workspace.href} className="home-workspace-card">
                <strong>{workspace.title}</strong>
                <span>{workspace.description}</span>
              </Link>
            ))}
          </div>
        </div>

        <div className="panel home-focus-panel">
          <h2>Research Focus</h2>
          <p>
            NewsLens is designed for exploratory analysis. It supports transparent comparisons of model behavior,
            source-level framing patterns, topic-controlled differences, and data quality signals without treating
            automated scores as final judgments.
          </p>
        </div>
      </section>
    </main>
  );
}
