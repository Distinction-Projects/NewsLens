export default function AboutPage() {
  return (
    <main>
      <h1>About This Project</h1>
      <p className="muted">Background, methodology, and current implementation direction for NewsLens.</p>

      <section className="panel">
        <h2>Project Profile</h2>
        <h3>James Vescovo</h3>
        <p className="muted">Computer Science Student at the University of Denver (Expected Graduation: May 2026)</p>
        <p>
          Focused on machine learning, data science, and interfaces that make technical analysis easier to inspect.
          NewsLens combines local sentiment experiments with a read-only AI news workflow driven by an external RSS
          pipeline.
        </p>
        <div className="badge-row">
          <span className="about-badge">Python</span>
          <span className="about-badge">Machine Learning</span>
          <span className="about-badge">RSS Pipelines</span>
          <span className="about-badge">Data Visualization</span>
        </div>
      </section>

      <section className="panel">
        <h2>Project History</h2>
        <div className="timeline-list">
          <article className="timeline-item">
            <h3>
              <span className="about-phase">Phase 1</span> Initial Research and Model Development
            </h3>
            <p>
              Explored sentiment analysis approaches, comparing VADER with machine learning classifiers such as Naive
              Bayes and SVM. Built the first local models and established baseline metrics using labeled training
              data.
            </p>
          </article>
          <article className="timeline-item">
            <h3>
              <span className="about-phase">Phase 2</span> Model Evaluation and Comparison
            </h3>
            <p>
              Implemented evaluation workflows for accuracy, precision, recall, and F1 score so local models could be
              compared consistently across corpora.
            </p>
          </article>
          <article className="timeline-item">
            <h3>
              <span className="about-phase">Phase 3</span> Web Application Development
            </h3>
            <p>
              Built the Dash interface for model testing, evaluation views, and interactive visual summaries in one
              application.
            </p>
          </article>
          <article className="timeline-item">
            <h3>
              <span className="about-phase">Phase 4</span> News Feed Integration
            </h3>
            <p>
              Integrated an external RSS pipeline published through GitHub Actions, added OpenAI-powered rubric
              scoring, and built read-only digest, stats, source, tag, workflow, raw JSON, and snapshot views that
              refresh from upstream JSON without rebuilding the deployment image.
            </p>
          </article>
          <article className="timeline-item">
            <h3>
              <span className="about-phase">Phase 5</span> Comparative Analysis <em>(Current)</em>
            </h3>
            <p>
              Current direction is comparing traditional sentiment models against upstream rubric outputs so the app
              can show where local classifiers agree with or diverge from richer multi-lens news analysis.
            </p>
          </article>
        </div>
      </section>

      <section className="panel">
        <h2>Technical Stack</h2>
        <div className="about-grid">
          <article className="about-card">
            <h3>Backend and ML</h3>
            <ul>
              <li>Python</li>
              <li>Scikit-Learn</li>
              <li>NLTK and VADER</li>
              <li>OpenAI API</li>
              <li>Pandas and NumPy</li>
            </ul>
          </article>
          <article className="about-card">
            <h3>Web Frameworks</h3>
            <ul>
              <li>Dash by Plotly (legacy surface)</li>
              <li>FastAPI (analytics API)</li>
              <li>Next.js (migration frontend)</li>
              <li>Plotly.js charts</li>
            </ul>
          </article>
          <article className="about-card">
            <h3>Deployment and Pipeline</h3>
            <ul>
              <li>DigitalOcean Droplet</li>
              <li>GitHub Version Control</li>
              <li>GitHub Actions RSS publishing</li>
              <li>Systemd and Nginx runtime</li>
            </ul>
          </article>
        </div>
      </section>

      <section className="panel">
        <h2>Project Method</h2>
        <ul>
          <li>Collect and normalize records from curated RSS feeds.</li>
          <li>Attach AI summaries, tags, and rubric scores from the upstream scoring pipeline.</li>
          <li>Derive source, lens, and topic analytics in backend services.</li>
          <li>Expose model-evaluation and news-analysis surfaces in one product.</li>
        </ul>
      </section>

      <section className="panel">
        <h2>Connect</h2>
        <div className="link-row">
          <a href="https://github.com/JamesVescovo24" target="_blank" rel="noreferrer">
            GitHub
          </a>
          <a href="https://www.linkedin.com/in/james-vescovo-2b168334b/" target="_blank" rel="noreferrer">
            LinkedIn
          </a>
        </div>
      </section>
    </main>
  );
}
