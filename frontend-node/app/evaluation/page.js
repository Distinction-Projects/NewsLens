import Link from "next/link";
import { fetchApiJson } from "../../lib/newsApi";

export const dynamic = "force-dynamic";

const DATASET_OPTIONS = [
  { key: "train5", label: "Train5 Corpus" },
  { key: "news", label: "News Corpus" }
];

function toPercent(value) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";
}

export default async function EvaluationPage({ searchParams }) {
  const datasetParam = typeof searchParams?.dataset === "string" ? searchParams.dataset : "train5";
  const selectedDataset = DATASET_OPTIONS.some((item) => item.key === datasetParam) ? datasetParam : "train5";
  const payload = await fetchApiJson(`/api/analysis/metrics?dataset=${encodeURIComponent(selectedDataset)}`, {
    cache: "no-store"
  });
  const data = payload?.data || {};
  const models = Array.isArray(data.models) ? data.models : [];

  return (
    <main>
      <h1>Model Evaluation</h1>
      <p className="muted">Evaluate sentiment model performance across supported corpora.</p>

      <div className="panel">
        <h2>Corpus</h2>
        <div className="news-nav-grid">
          {DATASET_OPTIONS.map((option) => {
            const active = option.key === selectedDataset;
            return (
              <Link
                key={option.key}
                href={`/evaluation?dataset=${option.key}`}
                className={`news-nav-link ${active ? "active-link" : ""}`}
              >
                {option.label}
              </Link>
            );
          })}
        </div>
      </div>

      <div className="panel">
        <h2>Summary</h2>
        <p className="muted">
          Dataset: <code>{data.display_name || selectedDataset}</code>
        </p>
        {models.length === 0 ? (
          <p className="muted">No model metrics found.</p>
        ) : (
          <div className="stats-grid">
            {models.map((row) => (
              <div key={row.key} className="stat-card">
                <span className="muted">{row.key}</span>
                <strong>Accuracy: {toPercent(row.accuracy)}</strong>
                <small className="muted">Precision (macro): {toPercent(row.precision_macro)}</small>
                <small className="muted">Recall (macro): {toPercent(row.recall_macro)}</small>
                <small className="muted">F1 (macro): {toPercent(row.f1_macro)}</small>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="panel">
        <h2>Model Details</h2>
        {models.length === 0 ? (
          <p className="muted">No model metrics found.</p>
        ) : (
          <div className="table-scroll">
            <table className="news-table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Accuracy</th>
                  <th>Precision (macro)</th>
                  <th>Recall (macro)</th>
                  <th>F1 (macro)</th>
                  <th>Confusion Matrix Shape</th>
                </tr>
              </thead>
              <tbody>
                {models.map((row) => {
                  const confusionRows = Array.isArray(row.confusion) ? row.confusion.length : 0;
                  const confusionCols =
                    confusionRows > 0 && Array.isArray(row.confusion[0]) ? row.confusion[0].length : 0;
                  return (
                    <tr key={row.key}>
                      <td>{row.key}</td>
                      <td>{toPercent(row.accuracy)}</td>
                      <td>{toPercent(row.precision_macro)}</td>
                      <td>{toPercent(row.recall_macro)}</td>
                      <td>{toPercent(row.f1_macro)}</td>
                      <td>
                        {confusionRows > 0 && confusionCols > 0 ? `${confusionRows} x ${confusionCols}` : "n/a"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
