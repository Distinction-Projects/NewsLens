const posterSections = [
  {
    title: "Introduction",
    body:
      "NewsLens investigates how automated sentiment models and AI-scored news lenses can support exploratory media analysis. The project focuses on transparent comparison rather than definitive judgments about outlet quality."
  },
  {
    title: "Research Question",
    body:
      "Can a public dashboard combine local sentiment models, rubric-based AI scoring, and controlled source comparisons to reveal interpretable differences in news framing?"
  },
  {
    title: "Methodology",
    body:
      "The system collects RSS articles, normalizes article metadata, scores articles across interpretable lenses, and computes backend-derived summaries for sources, topics, tags, events, and latent-space views."
  },
  {
    title: "Analysis",
    body:
      "Current analysis includes lens distributions, source-by-lens matrices, lens correlations, PCA/MDS projections, topic-controlled source comparisons, tag-controlled source comparisons, event-controlled comparisons, drift diagnostics, and tag momentum."
  },
  {
    title: "Key Results to Present",
    body:
      "The poster should highlight one or two clear examples: a topic-controlled source comparison, a lens PCA visualization, a tag momentum example, and an audit trail from aggregate metric to article-level evidence."
  },
  {
    title: "Limitations",
    body:
      "Scores are automated and should be interpreted as exploratory signals. Topic mix, event selection, prompt changes, model drift, and missing article text can affect results."
  },
  {
    title: "Future Work",
    body:
      "Planned work includes individual lens detail pages, stronger calibration, richer event matching, temporal centroid movement, Postgres-backed analytics snapshots, and additional uncertainty indicators."
  }
];

const paperSections = [
  {
    title: "Abstract",
    body:
      "This project presents NewsLens, a public research dashboard for comparing sentiment models and AI-assisted news analytics. The system combines RSS ingestion, rubric-based scoring, backend-derived statistical views, and a Next.js/FastAPI interface for interpretable exploratory analysis."
  },
  {
    title: "Introduction",
    body:
      "The paper should motivate the difficulty of comparing news sources when articles differ by topic, event, and editorial mix. NewsLens is framed as an analytic instrument for generating inspectable hypotheses about framing patterns."
  },
  {
    title: "Related Work",
    body:
      "Discuss sentiment analysis, media framing analysis, computational journalism tools, dimensionality reduction for exploratory data analysis, and the risks of automated scoring without calibration."
  },
  {
    title: "Data",
    body:
      "Describe the RSS-based corpus, article metadata, source labels, publication dates, topic tags, AI tags, scraped text, summaries, and scoring records. Include data-quality exclusions and missingness treatment."
  },
  {
    title: "Methods",
    body:
      "Explain the pipeline: article ingestion, normalization, local sentiment baselines, rubric/lens scoring, source aggregation, topic/tag duplication policies, event clustering, PCA/MDS latent views, FDR correction, drift diagnostics, and precomputed snapshots."
  },
  {
    title: "Evaluation Strategy",
    body:
      "Separate model evaluation from news interpretation. Report local sentiment model metrics where available, then describe exploratory validation checks such as topic controls, tag controls, same-event comparisons, stability diagnostics, and auditability."
  },
  {
    title: "Results",
    body:
      "Use selected dashboard outputs as figures: score distributions, source effects, topic-controlled differences, tag lens PCA, source/tag composition, trend charts, and event-controlled comparisons where data is sufficient."
  },
  {
    title: "Discussion",
    body:
      "Interpret outputs as patterns in lens-score space, not as direct measures of journalistic quality. Discuss where pooled differences collapse under topic or event control and where controlled differences persist."
  },
  {
    title: "Limitations",
    body:
      "Address automated scoring reliability, lack of human-grounded calibration, source selection bias, topic tagging noise, event-clustering uncertainty, model/prompt drift, and small-sample slices."
  },
  {
    title: "Future Work",
    body:
      "Add lens detail pages, improve event clustering, persist derived metrics in Postgres, add human or proxy calibration, track temporal movement of centroids, and expand uncertainty labels in the public interface."
  },
  {
    title: "Conclusion",
    body:
      "NewsLens demonstrates a practical architecture for transparent, controlled, exploratory news analysis while making the interpretive boundary conditions visible to users."
  }
];

const figureIdeas = [
  "System pipeline diagram from RSS feed to scoring to FastAPI to Next.js dashboard.",
  "Lens PCA or MDS map showing article/source positions in lens-score space.",
  "Topic-controlled source differentiation table or chart.",
  "Tag momentum chart showing recently accelerating tags.",
  "Source-tag composition matrix to contextualize source comparisons.",
  "Event-controlled comparison example showing same-story source differences."
];

const claimBoundaries = [
  "Use: source framing pattern, score distribution, topic-controlled difference, event-controlled comparison.",
  "Avoid: outlet quality ranking, truthfulness ranking, or definitive ideological classification.",
  "Always report sample size, control mode, missingness, and whether a view is pooled or controlled.",
  "Treat automated rubric scores as exploratory measures until calibration work is added."
];

function SectionCard({ title, body }) {
  return (
    <article className="research-section-card">
      <h3>{title}</h3>
      <p>{body}</p>
    </article>
  );
}

export default function ResearchPage() {
  return (
    <main className="research-page">
      <section className="research-hero panel">
        <p className="section-kicker">Poster and Paper Materials</p>
        <h1>NewsLens Research Writeup Hub</h1>
        <p className="muted">
          A single planning page for turning the NewsLens dashboard into a poster and paper. The copy here is designed
          to be edited into formal prose while preserving the project&apos;s methodology, interpretive boundaries, and
          future-work roadmap.
        </p>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Project Summary</p>
            <h2>One-Sentence Contribution</h2>
          </div>
        </div>
        <p>
          NewsLens is a public research dashboard that combines sentiment baselines, AI-assisted lens scoring, and
          controlled media analytics to make exploratory news-framing comparisons more transparent and auditable.
        </p>
        <div className="research-callout-grid">
          <div className="research-callout">
            <strong>Object of Study</strong>
            <span>RSS news articles scored across interpretable lenses.</span>
          </div>
          <div className="research-callout">
            <strong>Primary Method</strong>
            <span>Backend-derived comparisons by source, topic, tag, event, and latent lens geometry.</span>
          </div>
          <div className="research-callout">
            <strong>Interpretive Frame</strong>
            <span>Exploratory signal discovery, not final judgment or quality ranking.</span>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Poster Section</p>
            <h2>Poster Content Outline</h2>
          </div>
          <p className="muted compact-copy">Use these blocks as poster panels or slide sections.</p>
        </div>
        <div className="research-section-grid">
          {posterSections.map((section) => (
            <SectionCard key={section.title} title={section.title} body={section.body} />
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Paper Section</p>
            <h2>Paper Content Outline</h2>
          </div>
          <p className="muted compact-copy">A draft structure for a research paper or extended project report.</p>
        </div>
        <div className="research-paper-list">
          {paperSections.map((section, index) => (
            <article key={section.title} className="research-paper-row">
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div>
                <h3>{section.title}</h3>
                <p>{section.body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Figures</p>
            <h2>Suggested Figures and Tables</h2>
          </div>
        </div>
        <ul className="research-checklist">
          {figureIdeas.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Guardrails</p>
            <h2>Claim Boundaries</h2>
          </div>
        </div>
        <ul className="research-checklist">
          {claimBoundaries.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}
