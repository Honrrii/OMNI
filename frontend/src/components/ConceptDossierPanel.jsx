function getConceptDossierData(exportResult, missionResult) {
  const summary =
    exportResult?.export?.concept_dossier ||
    exportResult?.concept_dossier ||
    null;

  const manifest =
    exportResult?.export?.concept_dossier_manifest ||
    exportResult?.concept_dossier_manifest ||
    exportResult?.export?.artifacts?.concept_dossier_manifest ||
    exportResult?.artifacts?.concept_dossier_manifest ||
    missionResult?.artifacts?.concept_dossier_manifest ||
    null;

  return { summary, manifest };
}

// ── Primitives ─────────────────────────────────────────────────────────────

function CdChip({ label, variant }) {
  return <span className={`cd-chip cd-chip-${variant}`}>{label}</span>;
}

function CdSection({ label, children }) {
  return (
    <div className="cd-section">
      <span className="cd-section-label">{label}</span>
      <div className="cd-section-body">{children}</div>
    </div>
  );
}

function CdMetaCell({ label, value, highlight }) {
  return (
    <div className="cd-meta-cell">
      <span className="cd-meta-label">{label}</span>
      <span className={`cd-meta-value${highlight ? ` cd-meta-${highlight}` : ""}`}>
        {value}
      </span>
    </div>
  );
}

function CdItemRow({ label, value }) {
  return (
    <div className="cd-item-row">
      <span className="cd-item-label">{label}</span>
      <span className="cd-item-value">{value}</span>
    </div>
  );
}

function PanelStatusChip({ status }) {
  const variant =
    status === "available" ? "available" :
    status === "planned"   ? "planned"   :
    status === "missing"   ? "missing"   :
    "unknown";
  return (
    <span className={`cd-panel-status cd-panel-status-${variant}`}>
      {status ?? "unknown"}
    </span>
  );
}

// ── Dossier panel card ──────────────────────────────────────────────────────

function DossierPanelCard({ panel }) {
  if (!panel) return null;

  const items         = Array.isArray(panel.items)         ? panel.items         : [];
  const blockedClaims = Array.isArray(panel.blocked_claims) ? panel.blocked_claims : [];
  const brainSummary  = panel.summary && typeof panel.summary === "object" ? panel.summary : null;

  return (
    <div className={`cd-panel-card cd-panel-card-${panel.status || "unknown"}`}>
      <div className="cd-panel-card-header">
        <div className="cd-panel-card-title-row">
          <span className="cd-panel-card-title">{panel.title}</span>
          {panel.panel_type && (
            <span className="cd-panel-type">{panel.panel_type.replace(/_/g, " ")}</span>
          )}
        </div>
        <PanelStatusChip status={panel.status} />
      </div>

      {panel.render_hint && (
        <p className="cd-panel-render-hint">{panel.render_hint}</p>
      )}

      {panel.note && (
        <p className="cd-panel-note">{panel.note}</p>
      )}

      {/* items list — label/value pairs */}
      {items.length > 0 && (
        <ul className="cd-list">
          {items.map((item, i) => (
            <li key={i} className="cd-list-item">
              {item.label && <span className="cd-list-item-label">{item.label}</span>}
              {item.value ? <span className="cd-list-item-value">{item.value}</span> : null}
            </li>
          ))}
        </ul>
      )}

      {/* engineering brain summary counts */}
      {brainSummary && (
        <div className="cd-brain-summary">
          {brainSummary.selected_check_count != null && (
            <CdItemRow label="Selected checks" value={String(brainSummary.selected_check_count)} />
          )}
          {brainSummary.readiness_overall_status && (
            <CdItemRow label="Input readiness" value={brainSummary.readiness_overall_status} />
          )}
          {brainSummary.computed_metric_count != null && (
            <CdItemRow label="Computed metrics" value={String(brainSummary.computed_metric_count)} />
          )}
          {brainSummary.blocked_calculation_count != null && (
            <CdItemRow label="Blocked calculations" value={String(brainSummary.blocked_calculation_count)} />
          )}
        </div>
      )}

      {panel.gltf_preview_path && (
        <p className="cd-path">{panel.gltf_preview_path}</p>
      )}

      {blockedClaims.length > 0 && (
        <ul className="cd-blocked-list cd-blocked-list-inline">
          {blockedClaims.map((claim, i) => (
            <li key={i}>{claim}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Compact summary view (only summary available) ───────────────────────────

function CompactSummaryView({ summary }) {
  return (
    <div className="cd-compact">
      <div className="cd-meta-row">
        {summary.status && (
          <CdMetaCell label="Status" value={summary.status} />
        )}
        {summary.schema && (
          <CdMetaCell label="Schema" value={summary.schema} />
        )}
        {summary.panel_count != null && (
          <CdMetaCell label="Panels" value={String(summary.panel_count)} />
        )}
      </div>
      {summary.report_path && (
        <CdSection label="Report path">
          <p className="cd-path">{summary.report_path}</p>
        </CdSection>
      )}
    </div>
  );
}

// ── Rich manifest view (full manifest available) ────────────────────────────

function RichManifestView({ manifest }) {
  const panels        = Array.isArray(manifest.dossier_panels)     ? manifest.dossier_panels     : [];
  const allowedModes  = Array.isArray(manifest.allowed_visual_modes) ? manifest.allowed_visual_modes : [];
  const safetyNotes   = Array.isArray(manifest.safety_notes)       ? manifest.safety_notes       : [];
  const blockedClaims = Array.isArray(manifest.blocked_claims)     ? manifest.blocked_claims     : [];
  const sourceReports = manifest.source_reports && typeof manifest.source_reports === "object"
    ? Object.entries(manifest.source_reports)
    : [];
  const hero = manifest.hero_visual || null;

  return (
    <div className="cd-body">

      {/* ── Mission identity ── */}
      <div className="cd-meta-row">
        {manifest.mission_title && (
          <CdMetaCell label="Mission title" value={manifest.mission_title} />
        )}
        {manifest.platform_intent && (
          <CdMetaCell label="Platform" value={manifest.platform_intent} />
        )}
        {manifest.mission_type && (
          <CdMetaCell label="Mission type" value={manifest.mission_type} />
        )}
        <CdMetaCell
          label="Concept stage only"
          value={manifest.concept_stage_only ? "Yes" : "No"}
          highlight={manifest.concept_stage_only ? "yes" : "no"}
        />
        {manifest.schema && (
          <CdMetaCell label="Schema" value={manifest.schema} />
        )}
      </div>

      {/* ── Hero visual / visual preview contract ── */}
      {hero && (
        <CdSection label="Visual preview contract">
          <div className="cd-hero-row">
            <CdItemRow
              label="Type"
              value={hero.type ? hero.type.replace(/_/g, " ") : "—"}
            />
            <CdItemRow label="Label" value={hero.label ?? "—"} />
            {hero.path && (
              <CdItemRow label="Path" value={hero.path} />
            )}
            {hero.gltf_exists != null && (
              <CdItemRow
                label="GLTF file present"
                value={hero.gltf_exists ? "Yes" : "No — not yet generated"}
              />
            )}
            {hero.not_cad_accurate && (
              <CdItemRow
                label="CAD accuracy"
                value="Concept placeholder only. Not CAD-accurate."
              />
            )}
          </div>
        </CdSection>
      )}

      {/* ── Dossier panels ── */}
      {panels.length > 0 && (
        <CdSection label="Dossier panels">
          <div className="cd-detail-grid">
            {panels.map((panel) => (
              <DossierPanelCard key={panel.id || panel.title} panel={panel} />
            ))}
          </div>
        </CdSection>
      )}

      {/* ── Allowed visual modes ── */}
      {allowedModes.length > 0 && (
        <CdSection label="Allowed visual modes">
          <ul className="cd-mode-list">
            {allowedModes.map((mode, i) => (
              <li key={i}>
                <CdChip label={mode} variant="mode" />
              </li>
            ))}
          </ul>
        </CdSection>
      )}

      {/* ── Source reports ── */}
      {sourceReports.length > 0 && (
        <CdSection label="Source reports">
          <ul className="cd-source-list">
            {sourceReports.map(([key, file]) => (
              <li key={key}>
                <span className="cd-source-key">
                  {key.replace(/_/g, " ")}
                </span>
                <span className="cd-path">{file}</span>
              </li>
            ))}
          </ul>
        </CdSection>
      )}

      {/* ── Safety notes ── */}
      {safetyNotes.length > 0 && (
        <CdSection label="Safety notes">
          <ul className="cd-safe-list">
            {safetyNotes.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        </CdSection>
      )}

      {/* ── Blocked claims ── */}
      {blockedClaims.length > 0 && (
        <CdSection label="Blocked claims">
          <ul className="cd-blocked-list">
            {blockedClaims.map((claim, i) => (
              <li key={i}>{claim}</li>
            ))}
          </ul>
        </CdSection>
      )}

    </div>
  );
}

// ── Root component ──────────────────────────────────────────────────────────

export default function ConceptDossierPanel({ exportResult, missionResult }) {
  const { summary, manifest } = getConceptDossierData(exportResult, missionResult);

  if (!summary && !manifest) return null;

  if (summary?.status === "failed") {
    return (
      <div className="cd-panel cd-panel-failed">
        <div className="cd-header">
          <span className="cd-header-label">Concept Dossier</span>
        </div>
        <p className="cd-fail-note">
          Concept dossier export failed: {summary?.error || "unknown error"}.
        </p>
      </div>
    );
  }

  const hasManifest = !!manifest;

  return (
    <div className={`cd-panel${hasManifest ? " cd-panel-available" : " cd-panel-summary"}`}>

      {/* ── HUD bar ── */}
      <div className="cd-header">
        <span className="cd-header-label">Concept Dossier</span>
        <div className="cd-header-chips">
          <CdChip label="Concept-stage only" variant="concept" />
          <CdChip label="No engineering validation implied" variant="warn" />
          <CdChip label="Human review required" variant="review" />
        </div>
      </div>

      {/* ── Persistent safety notice ── */}
      <p className="cd-safety-banner">
        Concept dossier only. No engineering validation implied. No fabrication, flight,
        deployment, or operational readiness implied.
      </p>

      {/* ── Content ── */}
      {hasManifest
        ? <RichManifestView manifest={manifest} />
        : <CompactSummaryView summary={summary} />
      }
    </div>
  );
}
