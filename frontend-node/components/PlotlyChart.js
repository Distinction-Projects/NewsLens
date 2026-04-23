"use client";

import dynamic from "next/dynamic";

const Plot = dynamic(() => import("react-plotly.js"), {
  ssr: false
});

const DEFAULT_CONFIG = {
  displayModeBar: false,
  responsive: true
};

export default function PlotlyChart({ data = [], layout = {}, config = {}, className = "" }) {
  const titleValue = layout?.title;
  const hasTitle =
    (typeof titleValue === "string" && titleValue.trim().length > 0) ||
    (titleValue && typeof titleValue === "object" && typeof titleValue.text === "string" && titleValue.text.trim().length > 0);

  if (!hasTitle && process.env.NODE_ENV !== "production") {
    // Guardrail: all charts should provide a purpose-specific title.
    // Keep a fallback so users are never left with an unlabeled visualization.
    // eslint-disable-next-line no-console
    console.warn("PlotlyChart rendered without a title. Please pass layout.title for this graph.");
  }

  return (
    <div className={`plotly-chart ${className}`.trim()}>
      <Plot
        data={data}
        layout={{
          paper_bgcolor: "#0f1724",
          plot_bgcolor: "#0f1724",
          font: { color: "#d8e5ff" },
          margin: { l: 48, r: 24, t: 36, b: 48 },
          autosize: true,
          ...layout,
          title: hasTitle ? layout.title : "Visualization"
        }}
        config={{ ...DEFAULT_CONFIG, ...config }}
        style={{ width: "100%", height: "100%" }}
        useResizeHandler
      />
    </div>
  );
}
