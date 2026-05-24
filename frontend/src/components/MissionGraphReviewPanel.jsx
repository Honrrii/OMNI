function getGraphReview(exportResult) {
  return (
    exportResult?.export?.graph_review ||
    exportResult?.graph_review ||
    null
  );
}

function CoverageCard({ title, metrics }) {
  return (
    <div className="gr-coverage-card">
      <h4 className="gr-coverage-title">{title}</h4>
      <div className="gr-metrics">
        {metrics.map((m, i) => (
          <div key={i} className="gr-metric-row">
            <span className="gr-metric-label">{m.label}</span>
            <span className="gr-metric-value">{m.value ?? 0}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function IssueCard({ issue }) {
  const severity = issue.severity || "warning";
  return (
    <div className={`gr-issue-card gr-issue-${severity}`}>
      <div className="gr-issue-header">
        <code className="gr-issue-code">{issue.code}</code>
        <span className="gr-issue-category">{issue.category}</span>
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

export default function MissionGraphReviewPanel({ exportResult }) {
  const gr = getGraphReview(exportResult);

  if (!gr || gr.status !== "reviewed") {
    return (
      <div className="graph-review-panel gr-empty-state">
        <span className="gr-kicker">Mission Graph Review</span>
        <p className="gr-empty-message">
          No mission graph review available yet. Export a mission to generate one.
        </p>
      </div>
    );
  }

  const comp   = gr.component_coverage      || {};
  const ros2   = gr.ros2_coverage           || {};
  const morph  = gr.morphology_cad_coverage || {};
  const issues              = gr.issues               || [];
  const recommendations     = gr.recommendations      || [];
  const consistencyWarnings = gr.consistency_warnings || [];

  return (
    <section className="graph-review-panel">
      {/* Header */}
      <div className="gr-header">
        <div>
          <span className="gr-kicker">Mission Graph Review</span>
          <h2>Knowledge Graph Analysis</h2>
        </div>
        {gr.platform_normalized && (
          <div className="gr-platform-chip">
            {gr.platform_normalized}
          </div>
        )}
      </div>

      {/* Coverage cards */}
      <div className="gr-section">
        <p className="gr-section-label">Relationship Coverage</p>
        <div className="gr-coverage-grid">
          <CoverageCard
            title="Components"
            metrics={[
              { label: "Total",       value: comp.total },
              { label: "Power Rail",  value: comp.with_power_rail_id },
              { label: "Data Bus",    value: comp.with_data_bus_id },
              { label: "Body Region", value: comp.with_body_region_id },
            ]}
          />
          <CoverageCard
            title="ROS2 Nodes"
            metrics={[
              { label: "Total Nodes",           value: ros2.total_nodes },
              { label: "With Component Links",  value: ros2.nodes_with_component_ids },
            ]}
          />
          <CoverageCard
            title="Morphology / CAD"
            metrics={[
              { label: "Morphology",     value: morph.total_morphology },
              { label: "Body Regions",   value: morph.total_body_regions },
              { label: "CAD Features",   value: morph.total_cad_features },
              { label: "CAD w/ Region",  value: morph.cad_features_with_body_region_id },
            ]}
          />
        </div>
      </div>

      {/* Issues */}
      {issues.length > 0 && (
        <div className="gr-section">
          <p className="gr-section-label">Issues ({issues.length})</p>
          <div className="gr-issue-list">
            {issues.map((issue, i) => (
              <IssueCard key={i} issue={issue} />
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
