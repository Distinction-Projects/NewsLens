import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <h1>NewsLens Research Dashboard</h1>
      <p className="muted">
        Explore sentiment-model evaluation and AI-assisted news analysis through a public, read-only dashboard.
      </p>

      <div className="panel">
        <h2>Core Workspaces</h2>
        <ul>
          <li>
            <Link href="/evaluation">Model Evaluation</Link> compares sentiment model performance across corpora.
          </li>
          <li>
            <Link href="/text">Text Analysis</Link> runs focused sentiment checks on short passages.
          </li>
          <li>
            <Link href="/about">About</Link> explains the project method, data pipeline, and research boundaries.
          </li>
          <li>
            <Link href="/news">News Analytics</Link> provides source, topic, lens, and workflow diagnostics.
          </li>
        </ul>
      </div>

      <div className="panel">
        <h2>Research Focus</h2>
        <p>
          NewsLens is designed for exploratory analysis. It supports transparent comparisons of model behavior,
          source-level framing patterns, topic-controlled differences, and data quality signals without treating
          automated scores as final judgments.
        </p>
      </div>
    </main>
  );
}
