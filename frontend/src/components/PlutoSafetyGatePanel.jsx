function getPlutoSafetyGate(exportResult) {
  return (
    exportResult?.export?.cortex?.pluto_safety_gate ||
    exportResult?.cortex?.pluto_safety_gate ||
    exportResult?.export?.pluto_safety_gate ||
    exportResult?.pluto_safety_gate ||
    null
  );
}

function getPlutoSafetyGateFull(exportResult) {
  return (
    exportResult?.export?.artifacts?.pluto_safety_gate ||
    exportResult?.artifacts?.pluto_safety_gate ||
    null
  );
}

const STATUS_META = {
  passed:  { cls: "sg-status-passed",  label: "PASSED"  },
  warn:    { cls: "sg-status-warn",    label: "WARN"    },
  blocked: { cls: "sg-status-blocked", label: "BLOCKED" },
  failed:  { cls: "sg-status-failed",  label: "FAILED"  },
};

function StatusBadge({ status }) {
  const meta = STATUS_META[status] || { cls: "sg-status-warn", label: status?.toUpperCase() || "UNKNOWN" };
  return <span className={`sg-status-badge ${meta.cls}`}>{meta.label}</span>;
}

function Section({ label, children }) {
  return (
    <div className="sg-section">
      <span className="sg-section-label">{label}</span>
      <div className="sg-section-body">{children}</div>
    </div>
  );
}

function IssueList({ items, cls }) {
  if (!items || items.length === 0) return <span className="sg-empty">—</span>;
  return (
    <ul className="sg-issue-list">
      {items.map((item, i) => (
        <li key={i} className={`sg-issue-item ${cls}`}>{item}</li>
      ))}
    </ul>
  );
}

export default function PlutoSafetyGatePanel({ exportResult }) {
  const summary = getPlutoSafetyGate(exportResult);
  const full    = getPlutoSafetyGateFull(exportResult);

  if (!summary) return null;

  if (summary.status === "failed") {
    return (
      <div className="sg-panel sg-panel-failed">
        <div className="sg-hud-bar">
          <span className="sg-hud-label">Pluto Safety Gate</span>
        </div>
        <p className="sg-fail-note">
          Safety gate evaluation failed: {summary.error || "unknown error"}.
        </p>
      </div>
    );
  }

  const blockers   = full?.blockers              || [];
  const warnings   = full?.warnings              || [];
  const nextChecks = full?.required_next_checks  || [];
  const rationale  = full?.rationale             || "";
  const hasFullDetail = blockers.length > 0 || warnings.length > 0 || nextChecks.length > 0 || rationale;

  const reviewRequired = summary.required_human_review ?? full?.required_human_review ?? false;

  return (
    <div className={`sg-panel sg-panel-${summary.status || "warn"}`}>
      <div className="sg-hud-bar">
        <span className="sg-hud-label">Pluto Safety Gate</span>
        <div className="sg-hud-chips">
          <StatusBadge status={summary.status} />
          {summary.risk_level && (
            <span className={`sg-chip sg-risk-${summary.risk_level}`}>
              {summary.risk_level} risk
            </span>
          )}
          {reviewRequired && (
            <span className="sg-chip sg-chip-review">Human review required</span>
          )}
        </div>
      </div>

      <div className="sg-body">
        <div className="sg-meta-row">
          <div className="sg-meta-cell">
            <span className="sg-meta-label">Advisory status</span>
            <span className={`sg-meta-value sg-meta-status-${summary.status}`}>
              {summary.status || "—"}
            </span>
          </div>
          <div className="sg-meta-cell">
            <span className="sg-meta-label">Risk level</span>
            <span className="sg-meta-value">{summary.risk_level || "—"}</span>
          </div>
          <div className="sg-meta-cell">
            <span className="sg-meta-label">Human review required</span>
            <span className={`sg-meta-value ${reviewRequired ? "sg-review-yes" : "sg-review-no"}`}>
              {reviewRequired ? "Yes" : "No"}
            </span>
          </div>
        </div>

        {(summary.blocker_count > 0 || summary.warning_count > 0 || summary.next_check_count > 0) && (
          <div className="sg-count-row">
            {summary.blocker_count > 0 && (
              <span className="sg-count-chip sg-count-blocked">
                {summary.blocker_count} blocker{summary.blocker_count !== 1 ? "s" : ""}
              </span>
            )}
            {summary.warning_count > 0 && (
              <span className="sg-count-chip sg-count-warn">
                {summary.warning_count} warning{summary.warning_count !== 1 ? "s" : ""}
              </span>
            )}
            {summary.next_check_count > 0 && (
              <span className="sg-count-chip sg-count-check">
                {summary.next_check_count} next check{summary.next_check_count !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        )}

        {hasFullDetail && (
          <>
            {blockers.length > 0 && (
              <Section label="Blockers">
                <IssueList items={blockers} cls="sg-item-blocked" />
              </Section>
            )}
            {warnings.length > 0 && (
              <Section label="Warnings">
                <IssueList items={warnings} cls="sg-item-warn" />
              </Section>
            )}
            {nextChecks.length > 0 && (
              <Section label="Next checks">
                <IssueList items={nextChecks} cls="sg-item-check" />
              </Section>
            )}
            {rationale && (
              <Section label="Rationale">
                <p className="sg-rationale">{rationale}</p>
              </Section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
