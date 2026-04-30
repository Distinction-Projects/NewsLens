"use client";

import dynamic from "next/dynamic";

const Plot = dynamic(() => import("react-plotly.js"), {
  ssr: false
});

const DEFAULT_CONFIG = {
  displayModeBar: false,
  responsive: true
};

function normalizedTitle(titleValue) {
  if (typeof titleValue === "string") {
    return {
      text: titleValue,
      x: 0.02,
      xanchor: "left",
      y: 0.97,
      yanchor: "top",
      pad: { b: 18 }
    };
  }
  if (titleValue && typeof titleValue === "object") {
    return {
      x: 0.02,
      xanchor: "left",
      y: 0.97,
      yanchor: "top",
      pad: { b: 18 },
      ...titleValue
    };
  }
  return {
    text: "Visualization",
    x: 0.02,
    xanchor: "left",
    y: 0.97,
    yanchor: "top",
    pad: { b: 18 }
  };
}

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
          margin: { l: 56, r: 28, t: 82, b: 56 },
          autosize: true,
          ...layout,
          title: hasTitle ? normalizedTitle(layout.title) : normalizedTitle(null)
        }}
        config={{ ...DEFAULT_CONFIG, ...config }}
        style={{ width: "100%", height: "100%" }}
        useResizeHandler
      />
    </div>
  );
}
