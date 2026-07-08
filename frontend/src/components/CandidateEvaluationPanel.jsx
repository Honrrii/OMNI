function getCandidateEvaluation(exportResult) {
  return (
    exportResult?.export?.cortex?.candidate_evaluation ||
    exportResult?.cortex?.candidate_evaluation ||
    exportResult?.export?.candidate_evaluation ||
    exportResult?.candidate_evaluation ||
    null
  );
}

const AXIS_LABELS = {
  sky_score:   "Sky — Robotics / ROS2",
  isy_score:   "Isy — Physics / Control",
  korva_score: "Korva — Electronics",
  oli_score:   "Oli — CAD / Morphology",
  pluto_score: "Pluto — Safety / Risk",
  qaz_score:   "QaZ — Validation",
};

function ScoreBar({ label, value }) {
  const pct = Math.round((value ?? 0) * 100);
  const cls = pct >= 70 ? "ce-fill-good" : pct >= 40 ? "ce-fill-ok" : "ce-fill-low";
  return (
    <div className="ce-score-row">
      <span className="ce-score-label">{label}</span>
      <div className="ce-score-right">
        <div
          className="ce-meter-bar"
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${label}: ${pct}%`}
        >
          <div className={`ce-meter-fill ${cls}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="ce-score-value">{pct}%</span>
      </div>
    </div>
  );
}

function CandidateScoreCard({ evaluation }) {
  if (!evaluation) return null;
  return (
    <div className="ce-score-card">
      <div className="ce-score-card-name">{evaluation.name || evaluation.id}</div>
      {Object.entries(AXIS_LABELS).map(([key, label]) => (
        evaluation[key] !== undefined && (
          <ScoreBar key={key} label={label} value={evaluation[key]} />
        )
      ))}
    </div>
  );
}

export default function CandidateEvaluationPanel({ exportResult }) {
  const ce = getCandidateEvaluation(exportResult);

  if (!ce) return null;

  if (ce.status === "skipped") {
    return (
      <div className="ce-panel ce-panel-skipped">
        <p className="ce-skip-note">
          Candidate evaluation skipped — no structured design candidates available.
        </p>
      </div>
    );
  }

  if (ce.status === "failed") {
    return (
      <div className="ce-panel ce-panel-failed">
        <p className="ce-fail-note">
          Candidate evaluation failed: {ce.error || "unknown error"}.
        </p>
      </div>
    );
  }

  const evaluations = Array.isArray(ce.evaluations) ? ce.evaluations : [];
  const ranking = Array.isArray(ce.ranking) ? ce.ranking : [];
  const openQs = Array.isArray(ce.open_questions) ? ce.open_questions : [];
  const topThree = evaluations
    .slice()
    .sort((a, b) => (b.overall_score ?? 0) - (a.overall_score ?? 0))
    .slice(0, 3);

  return (
    <div className="ce-panel">
      <div className="ce-hud-bar">
        <span className="ce-hud-label">Candidate Evaluation</span>
        <div className="ce-hud-chips">
          <span className="ce-chip">{ce.candidates_evaluated ?? 0} evaluated</span>
          {ce.recommended_candidate_id && (
            <span className="ce-chip ce-chip-rec">
              Recommended: {ce.recommended_candidate_id}
            </span>
          )}
        </div>
      </div>

      {ce.council_summary && (
        <details className="p18m-details">
          <summary className="p18m-summary">Full candidate rationale</summary>
          <p className="ce-summary-text">{ce.council_summary}</p>
        </details>
      )}

      {ranking.length > 0 && (
        <div className="ce-section">
          <span className="ce-section-label">Ranking</span>
          <ol className="ce-ranking-list">
            {ranking.map((id, i) => (
              <li key={id} className={i === 0 ? "ce-rank-top" : "ce-rank-item"}>
                {id}
              </li>
            ))}
          </ol>
        </div>
      )}

      {topThree.length > 0 && (
        <div className="ce-section">
          <span className="ce-section-label">Council Scores — Top {topThree.length}</span>
          <div className="ce-score-grid">
            {topThree.map((ev) => (
              <CandidateScoreCard key={ev.id} evaluation={ev} />
            ))}
          </div>
        </div>
      )}

      {openQs.length > 0 && (
        <div className="ce-section">
          <span className="ce-section-label">Open Questions</span>
          <ul className="ce-open-questions">
            {openQs.map((q, i) => (
              <li key={i} className="ce-open-q">{q}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
