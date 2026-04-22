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
          ...layout
        }}
        config={{ ...DEFAULT_CONFIG, ...config }}
        style={{ width: "100%", height: "100%" }}
        useResizeHandler
      />
    </div>
  );
}
