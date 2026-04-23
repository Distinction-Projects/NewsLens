import Link from "next/link";
import { fetchApiJson } from "../../lib/newsApi";
import PlotlyChart from "../../components/PlotlyChart";

export const dynamic = "force-dynamic";

const DATASET_OPTIONS = [
  { key: "train5", label: "Train5 Corpus" },
  { key: "news", label: "News Corpus" }
];

const MODEL_OPTIONS = [
  { key: "naive bayes", label: "Naive Bayes" },
  { key: "svm", label: "SVM" },
  { key: "vader", label: "VADER" },
  { key: "openai", label: "OpenAI" }
];

function toPercent(value) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";
}

function toNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function titleCaseLabel(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "Unknown";
  }
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export default async function EvaluationPage({ searchParams }) {
  const datasetParam = typeof searchParams?.dataset === "string" ? searchParams.dataset : "train5";
  const selectedDataset = DATASET_OPTIONS.some((item) => item.key === datasetParam) ? datasetParam : "train5";
  const modelParam = typeof searchParams?.model === "string" ? searchParams.model : "naive bayes";
  const selectedModelKey = MODEL_OPTIONS.some((item) => item.key === modelParam) ? modelParam : "naive bayes";

  let data = {};
  let models = [];
  let apiError = null;
  try {
    const payload = await fetchApiJson(`/api/analysis/metrics?dataset=${encodeURIComponent(selectedDataset)}`);
    data = payload?.data || {};
    models = Array.isArray(data.models) ? data.models : [];
  } catch (error) {
    apiError = error instanceof Error ? error.message : String(error);
  }

  const labelsRaw = Array.isArray(data.labels) ? data.labels : [];
  const labels = labelsRaw.map((label) => titleCaseLabel(label));
  const selectedModel = models.find((row) => String(row?.key || "").toLowerCase() === selectedModelKey) || null;
  const selectedModelLabel = MODEL_OPTIONS.find((item) => item.key === selectedModelKey)?.label || selectedModelKey;
  const confusion = Array.isArray(selectedModel?.confusion) ? selectedModel.confusion : [];
  const precisionSeries = Array.isArray(selectedModel?.precision) ? selectedModel.precision.map((v) => toNumber(v) || 0) : [];
  const recallSeries = Array.isArray(selectedModel?.recall) ? selectedModel.recall.map((v) => toNumber(v) || 0) : [];
  const f1Series = Array.isArray(selectedModel?.f1) ? selectedModel.f1.map((v) => toNumber(v) || 0) : [];
  const hasCharts =
    labels.length > 0 &&
    confusion.length > 0 &&
    precisionSeries.length === labels.length &&
    recallSeries.length === labels.length &&
    f1Series.length === labels.length;

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
        <h2>Model</h2>
        <div className="news-nav-grid">
          {MODEL_OPTIONS.map((option) => {
            const active = option.key === selectedModelKey;
            return (
              <Link
                key={option.key}
                href={`/evaluation?dataset=${selectedDataset}&model=${encodeURIComponent(option.key)}`}
                className={`news-nav-link ${active ? "active-link" : ""}`}
              >
                {option.label}
              </Link>
            );
          })}
        </div>
      </div>

      {apiError ? (
        <div className="panel">
          <h2>API Error</h2>
          <p className="muted">{apiError}</p>
          <p>
            Ensure FastAPI is running: <code>uvicorn src.api.fastapi_app:app --reload --port 9000</code>
          </p>
        </div>
      ) : null}

      <div className="panel">
        <h2>Summary ({selectedModelLabel})</h2>
        <p className="muted">
          Dataset: <code>{data.display_name || selectedDataset}</code>
        </p>
        {models.length === 0 || !selectedModel ? (
          <p className="muted">No model metrics found.</p>
        ) : (
          <div className="stats-grid">
            <div className="stat-card">
              <span className="muted">Accuracy</span>
              <strong>{toPercent(selectedModel.accuracy)}</strong>
            </div>
            <div className="stat-card">
              <span className="muted">Precision (macro)</span>
              <strong>{toPercent(selectedModel.precision_macro)}</strong>
            </div>
            <div className="stat-card">
              <span className="muted">Recall (macro)</span>
              <strong>{toPercent(selectedModel.recall_macro)}</strong>
            </div>
            <div className="stat-card">
              <span className="muted">F1 (macro)</span>
              <strong>{toPercent(selectedModel.f1_macro)}</strong>
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <h2>Evaluation Visuals</h2>
        {!hasCharts ? (
          <p className="muted">Confusion matrix and class metric charts are unavailable for this selection.</p>
        ) : (
          <div className="chart-grid">
            <PlotlyChart
              data={[
                {
                  type: "heatmap",
                  z: confusion,
                  x: labels,
                  y: labels,
                  colorscale: "Greens",
                  hovertemplate: "Actual: %{y}<br>Predicted: %{x}<br>Count: %{z}<extra></extra>"
                }
              ]}
              layout={{
                title: "Confusion Matrix",
                xaxis: { title: "Predicted Label" },
                yaxis: { title: "Actual Label" }
              }}
            />
            <PlotlyChart
              data={[
                {
                  type: "bar",
                  name: "Precision",
                  x: labels,
                  y: precisionSeries,
                  marker: { color: "#636EFA" }
                },
                {
                  type: "bar",
                  name: "Recall",
                  x: labels,
                  y: recallSeries,
                  marker: { color: "#00CC96" }
                },
                {
                  type: "bar",
                  name: "F1-Score",
                  x: labels,
                  y: f1Series,
                  marker: { color: "#EF553B" }
                }
              ]}
              layout={{
                title: "Per-Class Metrics",
                barmode: "group",
                yaxis: { title: "Score", range: [0, 1] },
                xaxis: { title: "Class" }
              }}
            />
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
