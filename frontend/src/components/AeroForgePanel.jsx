function getAeroForgeData(exportResult, missionResult) {
  // Compact summary — preferred source
  const summary =
    exportResult?.export?.aeroforge ||
    exportResult?.aeroforge ||
    null;

  // Full intent report
  const intent =
    exportResult?.export?.artifacts?.aeroforge_intent ||
    exportResult?.artifacts?.aeroforge_intent ||
    missionResult?.artifacts?.aeroforge_intent ||
    null;

  // Full entry gate report
  const gate =
    exportResult?.export?.artifacts?.aeroforge_entry_gate ||
    exportResult?.artifacts?.aeroforge_entry_gate ||
    missionResult?.artifacts?.aeroforge_entry_gate ||
    null;

  return { summary, intent, gate };
}

function DomainChip({ label }) {
  return <span className="aeroforge-domain-chip">{label}</span>;
}

function GateChip({ label, variant }) {
  return (
    <span className={`aeroforge-gate-chip aeroforge-gate-chip-${variant}`}>
      {label}
    </span>
  );
}

function Section({ label, children }) {
  return (
    <div className="af-section">
      <span className="af-section-label">{label}</span>
      <div className="af-section-body">{children}</div>
    </div>
  );
}

function BlockedList({ items }) {
  if (!items || items.length === 0) return null;
  return (
    <ul className="aeroforge-blocked-list">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

function AllowedList({ items }) {
  if (!items || items.length === 0) return null;
  return (
    <ul className="af-allowed-list">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

export default function AeroForgePanel({ exportResult, missionResult }) {
  const { summary, intent, gate } = getAeroForgeData(exportResult, missionResult);

  // Nothing to show when not applicable, missing, or failed without useful data
  if (!summary && !intent) return null;

  const status = summary?.status ?? (intent?.status || "unknown");

  if (status === "not_applicable") return null;
  if (!summary?.aerospace_detected && !intent?.aerospace_detected) return null;

  if (status === "failed") {
    return (
      <div className="aeroforge-panel aeroforge-panel-failed">
        <div className="af-hud-bar">
          <span className="af-hud-label">AeroForge Concept Gate</span>
        </div>
        <p className="af-fail-note">
          AeroForge export failed: {summary?.error || "unknown error"}.
        </p>
      </div>
    );
  }

  const domains       = intent?.aero_domains       || [];
  const platformHint  = summary?.platform_hint     ?? intent?.platform_hint ?? null;
  const domainCount   = summary?.domain_count      ?? domains.length;
  const gateStatus    = summary?.entry_gate_status ?? gate?.status ?? null;
  const humanReview   = summary?.human_review_required ?? gate?.human_review_required ?? true;
  const conceptOnly   = summary?.concept_stage_only    ?? gate?.concept_stage_only    ?? true;
  const allowedOutputs  = intent?.allowed_outputs        || gate?.allowed_outputs  || [];
  const blockedOutputs  = intent?.blocked_outputs        || gate?.blocked_outputs  || [];
  const reviewGates     = intent?.required_review_gates  || [];
  const rationale       = intent?.rationale || gate?.rationale || "";
  const gateBlockers    = gate?.blockers || [];

  const gateVariant =
    gateStatus === "concept_stage_only" ? "concept" :
    gateStatus === "blocked"            ? "blocked"  :
    "unknown";

  return (
    <div className={`aeroforge-panel aeroforge-panel-${gateVariant}`}>
      <div className="af-hud-bar">
        <span className="af-hud-label">AeroForge Concept Gate</span>
        <div className="af-hud-chips">
          <GateChip label="Concept-stage only" variant="concept" />
          <GateChip label="Not flight-ready" variant="warn" />
          <GateChip label="Not fabrication-ready" variant="warn" />
          {humanReview && (
            <GateChip label="Human review required" variant="review" />
          )}
          {gateStatus && (
            <GateChip
              label={gateStatus.replace(/_/g, " ").toUpperCase()}
              variant={gateVariant}
            />
          )}
        </div>
      </div>

      <div className="af-body">
        <div className="af-meta-row">
          {platformHint && (
            <div className="af-meta-cell">
              <span className="af-meta-label">Platform hint</span>
              <span className="af-meta-value">{platformHint}</span>
            </div>
          )}
          <div className="af-meta-cell">
            <span className="af-meta-label">Domains detected</span>
            <span className="af-meta-value">{domainCount}</span>
          </div>
          <div className="af-meta-cell">
            <span className="af-meta-label">Concept stage only</span>
            <span className={`af-meta-value ${conceptOnly ? "af-yes" : "af-no"}`}>
              {conceptOnly ? "Yes" : "No"}
            </span>
          </div>
          <div className="af-meta-cell">
            <span className="af-meta-label">Human review required</span>
            <span className={`af-meta-value ${humanReview ? "af-yes" : "af-no"}`}>
              {humanReview ? "Yes" : "No"}
            </span>
          </div>
        </div>

        {domains.length > 0 && (
          <Section label="Aerospace domains">
            <div className="af-chip-wrap">
              {domains.map((d) => (
                <DomainChip key={d} label={d} />
              ))}
            </div>
          </Section>
        )}

        {gateBlockers.length > 0 && (
          <Section label="Entry gate blockers">
            <BlockedList items={gateBlockers} />
          </Section>
        )}

        {allowedOutputs.length > 0 && (
          <Section label="Allowed at concept stage">
            <AllowedList items={allowedOutputs} />
          </Section>
        )}

        {blockedOutputs.length > 0 && (
          <Section label="Blocked outputs">
            <BlockedList items={blockedOutputs} />
          </Section>
        )}

        {reviewGates.length > 0 && (
          <Section label="Required review gates">
            <ul className="af-review-gate-list">
              {reviewGates.map((g, i) => (
                <li key={i}>{g}</li>
              ))}
            </ul>
          </Section>
        )}

        {rationale && (
          <Section label="Rationale">
            <p className="af-rationale">{rationale}</p>
          </Section>
        )}
      </div>
    </div>
  );
}
