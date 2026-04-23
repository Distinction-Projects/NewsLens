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
    <form className="panel" onSubmit={onSubmit}>
      <h3>Analyze Text</h3>
      <p className="muted">Enter text and select a model to score sentiment.</p>

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
          <p>
            <strong>Sentiment:</strong> {result.sentiment_display || result.sentiment || "n/a"}
          </p>
          <p>
            <strong>Emotional Intensity Score:</strong> {typeof result.score === "number" ? result.score.toFixed(3) : "n/a"}
          </p>
          <p className="muted">
            <strong>Model:</strong> {result.model || model}
          </p>
        </div>
      ) : null}
    </form>
  );
}
