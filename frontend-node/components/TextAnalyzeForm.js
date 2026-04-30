"use client";

import { useState } from "react";
import { fetchApiJson } from "../lib/newsApi";

const MODEL_OPTIONS = ["Naive Bayes", "SVM", "VADER"];

export default function TextAnalyzeForm() {
  const [text, setText] = useState("");
  const [model, setModel] = useState("Naive Bayes");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const payload = await fetchApiJson("/api/analysis/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, model }),
        cache: "no-store"
      });
      setResult(payload?.data || null);
    } catch (requestError) {
      setError(requestError?.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="panel text-form-panel" onSubmit={onSubmit}>
      <div className="panel-heading">
        <div>
          <p className="section-kicker">Input</p>
          <h2>Analyze Text</h2>
        </div>
        <p className="muted compact-copy">Submit a sentence or paragraph and compare how the selected classifier scores its sentiment.</p>
      </div>

      <label className="form-label" htmlFor="text-input">
        Text
      </label>
      <textarea
        id="text-input"
        className="input-textarea"
        rows={6}
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="Type a sentence or paragraph..."
      />

      <label className="form-label" htmlFor="model-select">
        Model
      </label>
      <select id="model-select" className="input-select" value={model} onChange={(event) => setModel(event.target.value)}>
        {MODEL_OPTIONS.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>

      <button type="submit" className="news-nav-link button-link" disabled={loading || !text.trim()}>
        {loading ? "Analyzing..." : "Analyze"}
      </button>

      {error ? <p className="error-text">{error}</p> : null}

      {result ? (
        <div className="result-card">
          <p className="section-kicker">Result</p>
          <div className="text-result-grid">
            <div className="stat-card">
              <span className="muted">Sentiment</span>
              <strong>{result.sentiment_display || result.sentiment || "n/a"}</strong>
              <small className="muted">Predicted class label</small>
            </div>
            <div className="stat-card">
              <span className="muted">Emotional Intensity Score</span>
              <strong>{typeof result.score === "number" ? result.score.toFixed(3) : "n/a"}</strong>
              <small className="muted">Model-specific scalar output</small>
            </div>
            <div className="stat-card">
              <span className="muted">Model</span>
              <strong>{result.model || model}</strong>
              <small className="muted">Selected inference target</small>
            </div>
          </div>
        </div>
      ) : null}
    </form>
  );
}
