function getGraphReview(exportResult) {
  return (
    exportResult?.export?.graph_review ||
    exportResult?.graph_review ||
    null
  );
}

function getRos2Validation(exportResult) {
  return (
    exportResult?.export?.ros2_validation ||
    exportResult?.ros2_validation ||
    null
  );
}

function computeScore(gr) {
  if (!gr) return null;
  const comp  = gr.component_coverage      || {};
  const ros2  = gr.ros2_coverage           || {};
  const morph = gr.morphology_cad_coverage || {};

  const ratios = [];
  const ratio  = (v, d) => (d > 0 ? v / d : null);

  if (comp.total > 0) {
    [ratio(comp.with_power_rail_id, comp.total),
     ratio(comp.with_data_bus_id,   comp.total),
     ratio(comp.with_body_region_id, comp.total)].forEach(r => r !== null && ratios.push(r));
  }
  if (ros2.total_nodes > 0) {
    const r = ratio(ros2.nodes_with_component_ids, ros2.total_nodes);
    if (r !== null) ratios.push(r);
  }
  if (morph.total_cad_features > 0) {
    const r = ratio(morph.cad_features_with_body_region_id, morph.total_cad_features);
    if (r !== null) ratios.push(r);
  }
  if (ratios.length === 0) return null;
  return Math.round((ratios.reduce((a, b) => a + b, 0) / ratios.length) * 100);
}

function scoreVariant(score) {
  if (score === null) return "ob-score-na";
  if (score >= 80)    return "ob-score-good";
  if (score >= 50)    return "ob-score-mid";
  return "ob-score-low";
}

export default function OperatorBriefPanel({ missionResult, exportResult }) {
  const gr       = getGraphReview(exportResult);
  const ros2Val  = getRos2Validation(exportResult);
  const score    = computeScore(gr);
  const exported = !!exportResult;

  const platform  = gr?.platform_normalized || gr?.platform || null;
  const topIssues = (gr?.issues || []).slice(0, 3);
  const topRec    = (gr?.recommendations || [])[0] || null;
  const fileCount = exportResult?.export?.file_count ?? null;

  const chips = [];
  if (exported) {
    chips.push({ label: "Exported", cls: "ob-chip-ok" });
  }
  if (ros2Val !== null) {
    chips.push({
      label: ros2Val.passed ? "ROS2 Pass" : "ROS2 Needs Review",
      cls:   ros2Val.passed ? "ob-chip-ok" : "ob-chip-warn",
    });
  }
  if (gr?.status === "reviewed") {
    chips.push({ label: "Graph Reviewed", cls: "ob-chip-info" });
  }

  return (
    <div className="operator-brief-panel">

      <div className="ob-hud-bar">
        <span className="ob-hud-label">OPERATOR BRIEF</span>
        <div className="ob-chips">
          {chips.map((c, i) => (
            <span key={i} className={`ob-chip ${c.cls}`}>{c.label}</span>
          ))}
        </div>
      </div>

      <div className="ob-main-grid">

        <div className="ob-mission-col">
          <p className="ob-kicker">Mission Objective</p>
          <h2 className="ob-title">{missionResult.title}</h2>
          {platform && <span className="ob-platform-tag">{platform}</span>}
          {missionResult.fullMission && (
            <p className="ob-mission-text">
              {missionResult.fullMission.length > 180
                ? `${missionResult.fullMission.slice(0, 180).trim()}…`
                : missionResult.fullMission}
            </p>
          )}
        </div>

        <div className="ob-stats-col">
          {(exported || score !== null) && (
            <div className={`ob-score-chip ${scoreVariant(score)}`}>
              <span className="ob-score-number">{score !== null ? score : "N/A"}</span>
              <span className="ob-score-label">Graph Readiness</span>
            </div>
          )}

          {fileCount !== null && (
            <div className="ob-stat">
              <span className="ob-stat-value">{fileCount}</span>
              <span className="ob-stat-label">files exported</span>
            </div>
          )}

          {(missionResult.artifacts?.length ?? 0) > 0 && (
            <div className="ob-stat">
              <span className="ob-stat-value">{missionResult.artifacts.length}</span>
              <span className="ob-stat-label">artifacts</span>
            </div>
          )}
        </div>

      </div>

      {topIssues.length > 0 && (
        <div className="ob-row">
          <p className="ob-row-label">Top Issues</p>
          <div className="ob-issue-list">
            {topIssues.map((issue, i) => (
              <div key={i} className={`ob-issue-item ob-issue-${issue.severity || "warning"}`}>
                <code className="ob-issue-code">{issue.code}</code>
                <span className="ob-issue-msg">{issue.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {topRec && (
        <div className="ob-row">
          <p className="ob-row-label">Next Action</p>
          <p className="ob-rec-text">{topRec}</p>
        </div>
      )}

      {!exported && (
        <p className="ob-no-export">
          Export the mission to generate graph readiness, issue analysis, and full operator data.
        </p>
      )}

    </div>
  );
}
