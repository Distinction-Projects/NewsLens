import Link from "next/link";
import PlotlyChart from "../../components/PlotlyChart";
import { fetchApiJson } from "../../lib/newsApi";

export const dynamic = "force-dynamic";

const DATASET_OPTIONS = [
  { key: "train5", label: "Train5 Corpus" },
  { key: "news", label: "News Corpus" }
];

const MODEL_LABELS = {
  "naive bayes": "Naive Bayes",
  svm: "SVM",
  vader: "VADER",
  openai: "OpenAI"
};

function toPercent(value) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";
}

function titleCase(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function modelLabel(key) {
  return MODEL_LABELS[String(key || "").toLowerCase()] || titleCase(key);
}

function selectedModelKey(models, requestedModel) {
  if (!models.length) {
    return "";
  }
  const requested = String(requestedModel || "").trim().toLowerCase();
  const exact = models.find((row) => String(row.key || "").toLowerCase() === requested);
  return exact?.key || models[0].key;
}

function metricArray(row, key) {
  return Array.isArray(row?.[key]) ? row[key].map((value) => (typeof value === "number" ? value : Number(value) || 0)) : [];
}

function confusionChart(row, labels) {
  const displayLabels = labels.map(titleCase);
  const confusion = Array.isArray(row?.confusion) ? row.confusion : [];
  return {
    data: [
      {
        type: "heatmap",
        z: confusion,
        x: displayLabels,
        y: displayLabels,
        colorscale: "Greens",
        text: confusion,
        texttemplate: "%{text}",
        hovertemplate: "Actual: %{y}<br>Predicted: %{x}<br>Count: %{z}<extra></extra>"
      }
    ],
    layout: {
      title: `${modelLabel(row?.key)} Confusion Matrix`,
      xaxis: { title: "Predicted Label" },
      yaxis: { title: "Actual Label" },
      height: 360
    }
  };
}

function classMetricsChart(row, labels) {
  const displayLabels = labels.map(titleCase);
  return {
    data: [
      {
        type: "bar",
        name: "Precision",
        x: displayLabels,
        y: metricArray(row, "precision"),
        marker: { color: "#76a9fa" }
      },
      {
        type: "bar",
        name: "Recall",
        x: displayLabels,
        y: metricArray(row, "recall"),
        marker: { color: "#4dd3b0" }
      },
      {
        type: "bar",
        name: "F1",
        x: displayLabels,
        y: metricArray(row, "f1"),
        marker: { color: "#f5a66b" }
      }
    ],
    layout: {
      title: `${modelLabel(row?.key)} Per-Class Metrics`,
      barmode: "group",
      yaxis: { title: "Score", range: [0, 1] },
      xaxis: { title: "Class" },
      legend: { orientation: "h", y: 1.14 },
      height: 360
    }
  };
}

async function loadMetrics(selectedDataset) {
  try {
    const payload = await fetchApiJson(`/api/analysis/metrics?dataset=${encodeURIComponent(selectedDataset)}`);
    return { payload, error: null };
  } catch (error) {
    return { payload: null, error };
  }
}

export default async function EvaluationPage({ searchParams }) {
  const datasetParam = typeof searchParams?.dataset === "string" ? searchParams.dataset : "train5";
  const selectedDataset = DATASET_OPTIONS.some((item) => item.key === datasetParam) ? datasetParam : "train5";
  const requestedModel = typeof searchParams?.model === "string" ? searchParams.model : "";
  const { payload, error } = await loadMetrics(selectedDataset);
  const data = payload?.data || {};
  const models = Array.isArray(data.models) ? data.models : [];
  const activeModelKey = selectedModelKey(models, requestedModel);
  const activeModel = models.find((row) => row.key === activeModelKey) || null;
  const labels = Array.isArray(data.labels) ? data.labels : [];
  const confusion = activeModel ? confusionChart(activeModel, labels) : null;
  const classMetrics = activeModel ? classMetricsChart(activeModel, labels) : null;

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

      {error ? (
        <div className="panel">
          <h2>API Error</h2>
          <p className="error-text">{error.message || "Unable to load evaluation metrics."}</p>
        </div>
      ) : null}

      <div className="panel">
        <h2>Model</h2>
        {models.length === 0 ? (
          <p className="muted">No model metrics found.</p>
        ) : (
          <div className="news-nav-grid">
            {models.map((model) => {
              const active = model.key === activeModelKey;
              return (
                <Link
                  key={model.key}
                  href={`/evaluation?dataset=${encodeURIComponent(selectedDataset)}&model=${encodeURIComponent(model.key)}`}
                  className={`news-nav-link ${active ? "active-link" : ""}`}
                >
                  {modelLabel(model.key)}
                </Link>
              );
            })}
          </div>
        )}
      </div>

      <div className="panel">
        <h2>Summary</h2>
        <p className="muted">
          Dataset: <code>{data.display_name || selectedDataset}</code>
        </p>
        {!activeModel ? (
          <p className="muted">No model metrics found.</p>
        ) : (
          <div className="stats-grid">
            <div className="stat-card">
              <span className="muted">Model</span>
              <strong>{modelLabel(activeModel.key)}</strong>
              <small className="muted">Selected evaluation target</small>
            </div>
            <div className="stat-card">
              <span className="muted">Accuracy</span>
              <strong>{toPercent(activeModel.accuracy)}</strong>
              <small className="muted">Overall classification accuracy</small>
            </div>
            <div className="stat-card">
              <span className="muted">Precision</span>
              <strong>{toPercent(activeModel.precision_macro)}</strong>
              <small className="muted">Macro average</small>
            </div>
            <div className="stat-card">
              <span className="muted">Recall</span>
              <strong>{toPercent(activeModel.recall_macro)}</strong>
              <small className="muted">Macro average</small>
            </div>
            <div className="stat-card">
              <span className="muted">F1</span>
              <strong>{toPercent(activeModel.f1_macro)}</strong>
              <small className="muted">Macro average</small>
            </div>
          </div>
        )}
      </div>

      {confusion && classMetrics ? (
        <div className="panel">
          <h2>Evaluation Visuals</h2>
          <div className="chart-grid">
            <PlotlyChart data={confusion.data} layout={confusion.layout} />
            <PlotlyChart data={classMetrics.data} layout={classMetrics.layout} />
          </div>
        </div>
      ) : null}

      <div className="panel">
        <h2>All Model Details</h2>
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
                      <td>{modelLabel(row.key)}</td>
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
