export default function AboutPage() {
  return (
    <main>
      <h1>About This Project</h1>
      <p className="muted">
        NewsLens combines local sentiment-model experimentation with a read-only AI news workflow driven by an
        external RSS pipeline.
      </p>

      <section className="panel">
        <h2>Project Method</h2>
        <ul>
          <li>Collect and normalize news records from curated RSS feeds.</li>
          <li>Attach AI summaries, tags, and rubric scores from the upstream scoring pipeline.</li>
          <li>Derive comparable source/lens/topic analytics in backend services.</li>
          <li>Expose both model-evaluation views and news-analysis views in the same product.</li>
        </ul>
      </section>

      <section className="panel">
        <h2>Current Stack Direction</h2>
        <ul>
          <li>Backend: FastAPI endpoints for news and local sentiment analytics.</li>
          <li>Frontend: Next.js migration surface replacing Dash routes incrementally.</li>
          <li>Data: JSON contract outputs from RSS_Feeds plus local model artifacts.</li>
        </ul>
      </section>
    </main>
  );
}
