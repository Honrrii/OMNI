function getGraphReview(exportResult) {
  return (
    exportResult?.export?.graph_review ||
    exportResult?.graph_review ||
    null
  );
}

function computeReadinessScore(comp, ros2, morph) {
  const ratios = [];
  const t = (v, d) => d > 0 ? v / d : null;

  if (comp.total > 0) {
    const r1 = t(comp.with_power_rail_id,  comp.total);
    const r2 = t(comp.with_data_bus_id,    comp.total);
    const r3 = t(comp.with_body_region_id, comp.total);
    if (r1 !== null) ratios.push(r1);
    if (r2 !== null) ratios.push(r2);
    if (r3 !== null) ratios.push(r3);
  }
  if (ros2.total_nodes > 0) {
    const r = t(ros2.nodes_with_component_ids, ros2.total_nodes);
    if (r !== null) ratios.push(r);
  }
  if (morph.total_cad_features > 0) {
    const r = t(morph.cad_features_with_body_region_id, morph.total_cad_features);
    if (r !== null) ratios.push(r);
  }
  if (ratios.length === 0) return null;
  return Math.round((ratios.reduce((a, b) => a + b, 0) / ratios.length) * 100);
}

function ringColor(score) {
  if (score >= 80) return "#7cffc8";
  if (score >= 50) return "#4da3ff";
  return "#ffbf4a";
}

// ── Coverage ──────────────────────────────────────────────

function CoverageMetric({ label, value, denominator }) {
  const v   = value ?? 0;
  const pct = denominator > 0 ? Math.round((v / denominator) * 100) : null;
  return (
    <div className="gr-metric-row">
      <span className="gr-metric-label">{label}</span>
      <div className="gr-metric-right">
        {pct !== null && (
          <div
            className="gr-meter-bar"
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${label}: ${pct}%`}
          >
            <div
              className={`gr-meter-fill ${pct >= 70 ? "gr-fill-good" : pct >= 40 ? "gr-fill-ok" : "gr-fill-low"}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        )}
        <span className="gr-metric-value">
          {denominator !== undefined ? `${v} / ${denominator}` : v}
        </span>
      </div>
    </div>
  );
}

function CoverageCard({ title, metrics }) {
  return (
    <div className="gr-coverage-card">
      <h4 className="gr-coverage-title">{title}</h4>
      <div className="gr-metrics">
        {metrics.map((m, i) => (
          <CoverageMetric key={i} {...m} />
        ))}
      </div>
    </div>
  );
}

// ── Issues ────────────────────────────────────────────────

const CATEGORY_META = {
  component: { label: "Component", cls: "gr-cat-sky"  },
  ros2:      { label: "ROS2",      cls: "gr-cat-echo" },
  cad:       { label: "CAD",       cls: "gr-cat-vega" },
};
const CATEGORY_ORDER = ["component", "ros2", "cad"];

function IssueCard({ issue }) {
  const severity = issue.severity || "warning";
  const catMeta  = CATEGORY_META[issue.category] || { label: issue.category || "other", cls: "gr-cat-muted" };
  return (
    <div className={`gr-issue-card gr-issue-${severity}`}>
      <div className="gr-issue-header">
        <code className="gr-issue-code">{issue.code}</code>
        <span className={`gr-category-badge ${catMeta.cls}`}>{catMeta.label}</span>
        <span className={`gr-severity-badge gr-sev-${severity}`}>{severity}</span>
      </div>
      <p className="gr-issue-message">{issue.message}</p>
      {issue.related_ids?.length > 0 && (
        <div className="gr-issue-ids">
          {issue.related_ids.map((id, i) => (
            <code key={i} className="gr-related-id">{id}</code>
          ))}
        </div>
      )}
    </div>
  );
}

function IssueGroup({ category, issues }) {
  const meta = CATEGORY_META[category] || { label: category, cls: "gr-cat-muted" };
  return (
    <div className="gr-issue-group">
      <div className="gr-issue-group-head">
        <span className={`gr-category-badge ${meta.cls}`}>{meta.label}</span>
        <span className="gr-issue-group-count">{issues.length}</span>
      </div>
      <div className="gr-issue-list">
        {issues.map((issue, i) => <IssueCard key={i} issue={issue} />)}
      </div>
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────

export default function MissionGraphReviewPanel({ exportResult }) {
  const gr = getGraphReview(exportResult);

  if (!gr || gr.status !== "reviewed") {
    return (
      <div className="graph-review-panel gr-empty-state">
        <h2>Mission graph review</h2>
        <p className="gr-empty-message">
          No mission graph review available yet. Export a mission to generate one.
        </p>
      </div>
    );
  }

  const comp  = gr.component_coverage      || {};
  const ros2  = gr.ros2_coverage           || {};
  const morph = gr.morphology_cad_coverage || {};
  const issues              = gr.issues               || [];
  const recommendations     = gr.recommendations      || [];
  const consistencyWarnings = gr.consistency_warnings || [];

  const score = computeReadinessScore(comp, ros2, morph);
  const color = score !== null ? ringColor(score) : "#555e7a";

  // Group issues by category
  const grouped = {};
  for (const issue of issues) {
    const cat = issue.category || "other";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(issue);
  }
  const groupOrder = [
    ...CATEGORY_ORDER,
    ...Object.keys(grouped).filter(k => !CATEGORY_ORDER.includes(k)),
  ];

  return (
    <section className="graph-review-panel">

      {/* HUD status bar */}
      <div className="gr-hud-bar">
        <div className="gr-hud-chips">
          {gr.platform_normalized && (
            <span className="gr-platform-chip">{gr.platform_normalized}</span>
          )}
          {issues.length > 0 && (
            <span className="gr-hud-badge gr-badge-issues">{issues.length} issues</span>
          )}
          {recommendations.length > 0 && (
            <span className="gr-hud-badge gr-badge-recs">{recommendations.length} recs</span>
          )}
        </div>
      </div>

      {/* Main header */}
      <div className="gr-header">
        <div>
          <span className="gr-kicker">Mission Graph Review</span>
          <h2>Knowledge Graph Analysis</h2>
        </div>
        <div
          className="gr-readiness-ring"
          style={{ "--gr-score-pct": score === null ? "0%" : `${score}%`, "--gr-ring-color": color }}
          aria-label={score === null ? "Graph readiness score: N/A" : `Graph readiness score: ${score} of 100`}
        >
          <span className="gr-readiness-number">{score === null ? "N/A" : score}</span>
          <span className="gr-readiness-label">READINESS</span>
        </div>
      </div>

      {/* Coverage cards */}
      <div className="gr-section">
        <p className="gr-section-label">Relationship Coverage</p>
        <div className="gr-coverage-grid">
          <CoverageCard
            title="Components"
            metrics={[
              { label: "Total",       value: comp.total },
              { label: "Power Rail",  value: comp.with_power_rail_id,  denominator: comp.total },
              { label: "Data Bus",    value: comp.with_data_bus_id,    denominator: comp.total },
              { label: "Body Region", value: comp.with_body_region_id, denominator: comp.total },
            ]}
          />
          <CoverageCard
            title="ROS2 Nodes"
            metrics={[
              { label: "Total",                 value: ros2.total_nodes },
              { label: "With Component Links",  value: ros2.nodes_with_component_ids, denominator: ros2.total_nodes },
            ]}
          />
          <CoverageCard
            title="Morphology / CAD"
            metrics={[
              { label: "Morphology",    value: morph.total_morphology },
              { label: "Body Regions",  value: morph.total_body_regions },
              { label: "CAD Features",  value: morph.total_cad_features },
              { label: "CAD w/ Region", value: morph.cad_features_with_body_region_id, denominator: morph.total_cad_features },
            ]}
          />
        </div>
      </div>

      {/* Issues — grouped by category */}
      {issues.length > 0 && (
        <div className="gr-section">
          <p className="gr-section-label">Issues ({issues.length})</p>
          <div className="gr-issue-groups">
            {groupOrder.map(cat => grouped[cat] && (
              <IssueGroup key={cat} category={cat} issues={grouped[cat]} />
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div className="gr-section">
          <p className="gr-section-label">Recommendations</p>
          <ul className="gr-rec-list">
            {recommendations.map((rec, i) => (
              <li key={i}>{rec}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Consistency warnings */}
      {consistencyWarnings.length > 0 && (
        <div className="gr-section">
          <p className="gr-section-label">Graph Consistency Warnings</p>
          <ul className="gr-consistency-list">
            {consistencyWarnings.map((w, i) => (
              <li key={i}>
                <code>{w.code}</code> — {w.message}
              </li>
            ))}
          </ul>
        </div>
      )}

    </section>
  );
}
