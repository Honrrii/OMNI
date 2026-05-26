function getMissionIntent(exportResult) {
  return (
    exportResult?.export?.cortex?.mission_intent ||
    exportResult?.cortex?.mission_intent ||
    exportResult?.export?.mission_intent ||
    exportResult?.mission_intent ||
    null
  );
}

function getMissionIntentFull(exportResult) {
  // The summary in cortex only carries counts; full detail lives in the
  // mission_intent artifact if the supervisor wired it into artifacts.
  return (
    exportResult?.export?.artifacts?.mission_intent ||
    exportResult?.artifacts?.mission_intent ||
    null
  );
}

function TagList({ items }) {
  if (!items || items.length === 0) return <span className="mi-empty">—</span>;
  return (
    <ul className="mi-tag-list">
      {items.map((item, i) => (
        <li key={i} className="mi-tag">{item}</li>
      ))}
    </ul>
  );
}

function Section({ label, children }) {
  return (
    <div className="mi-section">
      <span className="mi-section-label">{label}</span>
      <div className="mi-section-body">{children}</div>
    </div>
  );
}

export default function MissionIntentPanel({ exportResult }) {
  const summary = getMissionIntent(exportResult);
  const full    = getMissionIntentFull(exportResult);

  if (!summary) return null;

  if (summary.status === "failed") {
    return (
      <div className="mi-panel mi-panel-failed">
        <p className="mi-fail-note">
          Mission intent compilation failed: {summary.error || "unknown error"}.
        </p>
      </div>
    );
  }

  const domains     = full?.detected_domains      || [];
  const sensing     = full?.sensing_requirements  || [];
  const outputs     = full?.required_outputs      || [];
  const environment = full?.operating_environment || [];
  const mobility    = full?.mobility_requirements || [];
  const questions   = full?.open_questions        || [];

  const hasFullDetail = domains.length > 0 || sensing.length > 0 || outputs.length > 0;

  return (
    <div className="mi-panel">
      <div className="mi-hud-bar">
        <span className="mi-hud-label">What OMNI thinks the mission means</span>
        <div className="mi-hud-chips">
          {summary.mission_type && (
            <span className="mi-chip">{summary.mission_type}</span>
          )}
          {summary.platform_intent && (
            <span className="mi-chip mi-chip-platform">{summary.platform_intent}</span>
          )}
          {summary.detected_domain_count > 0 && (
            <span className="mi-chip">
              {summary.detected_domain_count} domain{summary.detected_domain_count !== 1 ? "s" : ""}
            </span>
          )}
          {summary.open_question_count > 0 && (
            <span className="mi-chip mi-chip-warn">
              {summary.open_question_count} open question{summary.open_question_count !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      </div>

      <div className="mi-body">
        <div className="mi-meta-row">
          <div className="mi-meta-cell">
            <span className="mi-meta-label">Platform intent</span>
            <span className="mi-meta-value">{summary.platform_intent || "unknown"}</span>
          </div>
          <div className="mi-meta-cell">
            <span className="mi-meta-label">Mission type</span>
            <span className="mi-meta-value">{summary.mission_type || "—"}</span>
          </div>
        </div>

        {hasFullDetail && (
          <>
            {domains.length > 0 && (
              <Section label="Detected domains">
                <TagList items={domains} />
              </Section>
            )}

            {sensing.length > 0 && (
              <Section label="Sensing requirements">
                <TagList items={sensing} />
              </Section>
            )}

            {outputs.length > 0 && (
              <Section label="Required outputs">
                <TagList items={outputs} />
              </Section>
            )}

            {environment.length > 0 && (
              <Section label="Operating environment">
                <TagList items={environment} />
              </Section>
            )}

            {mobility.length > 0 && (
              <Section label="Mobility">
                <TagList items={mobility} />
              </Section>
            )}

            {questions.length > 0 && (
              <Section label="Missing information">
                <ul className="mi-questions">
                  {questions.map((q, i) => (
                    <li key={i} className="mi-question">{q}</li>
                  ))}
                </ul>
              </Section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
