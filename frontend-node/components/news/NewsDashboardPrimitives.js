import {
  dataModeQueryHref,
  formatNumber,
  normalizeDataMode,
  selectedSnapshotDateValue,
  snapshotDateFromSearchParams,
  toNumber
} from "../../lib/newsPageUtils";

export function PageIntro({ summary }) {
  return (
    <details className="news-page-intro">
      <summary>What this page does</summary>
      <p className="muted">{summary}</p>
    </details>
  );
}

export function DataModeControls({ searchParams, extraParams = {} }) {
  const dataMode = normalizeDataMode(searchParams);
  const snapshotDateValue = selectedSnapshotDateValue(searchParams);
  const missingSnapshot = dataMode === "snapshot" && !snapshotDateFromSearchParams(searchParams);
  const currentHref = dataModeQueryHref("current", snapshotDateValue, extraParams);
  const snapshotHref = dataModeQueryHref("snapshot", snapshotDateValue, extraParams);
  return (
    <div className="panel">
      <h3>Data Mode</h3>
      <div className="top-nav-links">
        <a className={`news-nav-link ${dataMode === "current" ? "active-link" : ""}`} href={currentHref}>
          Current
        </a>
        <a className={`news-nav-link ${dataMode === "snapshot" ? "active-link" : ""}`} href={snapshotHref}>
          Snapshot
        </a>
      </div>
      <form method="get" style={{ marginTop: "10px" }}>
        {Object.entries(extraParams).map(([key, value]) => (
          <input key={key} type="hidden" name={key} value={String(value || "")} />
        ))}
        <input type="hidden" name="data_mode" value={dataMode} />
        <label className="muted" htmlFor="snapshot-date-input">
          Snapshot date
        </label>
        <div style={{ display: "flex", gap: "10px", alignItems: "center", marginTop: "6px" }}>
          <input
            id="snapshot-date-input"
            name="snapshot"
            type="date"
            defaultValue={snapshotDateValue}
            disabled={dataMode !== "snapshot"}
          />
          <button type="submit" className="news-nav-link">
            Apply
          </button>
        </div>
      </form>
      {missingSnapshot ? (
        <p className="muted" style={{ marginTop: "10px" }}>
          Snapshot mode requires a valid date (`YYYY-MM-DD`). Falling back to current data until provided.
        </p>
      ) : null}
    </div>
  );
}

export function StatCard({ label, value, detail }) {
  return (
    <div className="stat-card">
      <span className="muted">{label}</span>
      <strong>{value}</strong>
      {detail ? <small className="muted">{detail}</small> : null}
    </div>
  );
}

export function StatusPill({ children, tone = "neutral" }) {
  return <span className={`status-pill ${tone}`}>{children}</span>;
}

export function EmptyState({ children = "No data available." }) {
  return <p className="muted">{children}</p>;
}

export function StatusBlock({ status, reason }) {
  const tone = status === "ok" ? "good" : "bad";
  return (
    <p className="muted">
      <StatusPill tone={tone}>{status || "unknown"}</StatusPill>
      {reason ? ` ${reason}` : ""}
    </p>
  );
}

export function MiniBar({ value, max }) {
  const number = toNumber(value) || 0;
  const limit = Math.max(toNumber(max) || 0, number, 1);
  const width = Math.max(0, Math.min(100, (number / limit) * 100));
  return (
    <div className="mini-bar" aria-label={`${formatNumber(number)} of ${formatNumber(limit)}`}>
      <span style={{ width: `${width}%` }} />
    </div>
  );
}
