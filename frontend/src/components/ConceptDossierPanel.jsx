import ConceptDossierBlueprintBoard from "./ConceptDossierBlueprintBoard.jsx";

function buildArtifactSummaries(exportResult) {
  const exp = exportResult?.export || exportResult || {};
  return {
    fusion360:            exp.fusion360_generation             || null,
    kicad:                exp.kicad_generation                 || null,
    ros2:                 exp.ros2_generation                  || null,
    ros2_validation:      exp.ros2_validation                  || null,
    visual_bay:           exp.visual_bay                       || null,
    concept_dossier:      exp.concept_dossier                  || null,
    morphology:           exp.morphology_validation            || null,
    candidate_evaluation: exp.cortex?.candidate_evaluation     || null,
    engineering_brain:    exp.engineering_brain                || null,
    files:                Array.isArray(exp.files) ? exp.files : [],
  };
}

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

const CD_CHIP_DS_MAP = {
  concept: "concept",
  warn:    "warning",
  review:  "info",
  mode:    "muted",
};

function CdChip({ label, variant }) {
  const dsVariant = CD_CHIP_DS_MAP[variant] || "muted";
  return (
    <span className={`cd-chip cd-chip-${variant} omni-ds-chip omni-ds-chip-${dsVariant}`}>
      {label}
    </span>
  );
}

function CdSection({ label, children }) {
  return (
    <div className="cd-section omni-ds-section">
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

// ── Hero meta item ──────────────────────────────────────────────────────────

function HeroMetaItem({ label, value, accentYes, accentNo, mono }) {
  let cls = "cd-hero-meta-v";
  if (accentYes) cls += " cd-hero-meta-accent-yes";
  if (accentNo)  cls += " cd-hero-meta-accent-no";
  if (mono)      cls += " cd-hero-meta-mono";
  return (
    <div className="cd-hero-meta-item">
      <span className="cd-hero-meta-k">{label}</span>
      <span className={cls}>{value}</span>
    </div>
  );
}

// ── Concept Dossier Hero / Reveal ───────────────────────────────────────────
// Aerospace-style concept reveal section.
// Concept-stage only. No engineering validation implied.

function ConceptDossierHero({ manifest, summary }) {
  const title       = manifest?.mission_title || null;
  const platform    = manifest?.platform_intent || null;
  const missionType = manifest?.mission_type || null;
  const schema      = manifest?.schema || summary?.schema || null;
  const status      = summary?.status || null;
  const conceptOnly = manifest?.concept_stage_only ?? null;
  const hero        = manifest?.hero_visual || null;
  const notCadAcc   = !!(hero?.not_cad_accurate || manifest?.not_cad_accurate);
  const allowedModes = Array.isArray(manifest?.allowed_visual_modes)
    ? manifest.allowed_visual_modes : [];
  const panels       = Array.isArray(manifest?.dossier_panels)
    ? manifest.dossier_panels : [];
  const fallbackCount = !panels.length
    ? (manifest?.panel_count ?? summary?.panel_count ?? null) : null;
  const reportPath  = !manifest ? (summary?.report_path || null) : null;

  const isObj    = p => p && typeof p === "object" && !Array.isArray(p);
  const nAvail   = panels.filter(p => isObj(p) && p.status === "available").length;
  const nPlanned = panels.filter(p => isObj(p) && p.status === "planned").length;
  const nMissing = panels.filter(p => isObj(p) && p.status === "missing").length;
  const nFailed  = panels.filter(p => isObj(p) && p.status === "failed").length;

  const hasContent =
    title || platform || missionType || schema || status ||
    conceptOnly != null || hero || panels.length > 0 ||
    fallbackCount != null || allowedModes.length > 0 || reportPath;

  if (!hasContent) return null;

  return (
    <div className="cd-hero" role="region" aria-label="Concept dossier reveal">

      {/* Kicker */}
      <div className="cd-hero-kicker">
        <span aria-hidden="true" className="cd-hero-kicker-icon">◈</span>
        {manifest ? "Mission Concept Reveal" : "Concept Dossier"}
      </div>

      {/* Title */}
      {title && <h3 className="cd-hero-title">{title}</h3>}

      {/* Meta + visual preview grid */}
      <div className="cd-hero-grid">
        {(platform || missionType || schema || status || conceptOnly != null || reportPath) && (
          <div className="cd-hero-meta">
            {platform    && <HeroMetaItem label="Platform"         value={platform} />}
            {missionType && <HeroMetaItem label="Mission type"     value={missionType} />}
            {schema      && <HeroMetaItem label="Schema"           value={schema} />}
            {status      && <HeroMetaItem label="Status"           value={status} />}
            {conceptOnly != null && (
              <HeroMetaItem
                label="Concept stage only"
                value={conceptOnly ? "Yes" : "No"}
                accentYes={!!conceptOnly}
                accentNo={!conceptOnly}
              />
            )}
            {reportPath && <HeroMetaItem label="Report" value={reportPath} mono />}
          </div>
        )}

        {hero && (
          <div className="cd-hero-visual">
            <span className="cd-hero-visual-eyebrow">Visual preview</span>
            {typeof hero.type === "string" && hero.type && (
              <div className="cd-hero-visual-row">
                <span className="cd-hero-visual-k">Type</span>
                <span className="cd-hero-visual-v">{hero.type.replace(/_/g, " ")}</span>
              </div>
            )}
            {hero.label && (
              <div className="cd-hero-visual-row">
                <span className="cd-hero-visual-k">Label</span>
                <span className="cd-hero-visual-v">{hero.label}</span>
              </div>
            )}
            {hero.gltf_exists != null && (
              <div className="cd-hero-visual-row">
                <span className="cd-hero-visual-k">GLTF</span>
                <span className={`cd-hero-visual-v ${hero.gltf_exists ? "cd-hero-vv-present" : "cd-hero-vv-absent"}`}>
                  {hero.gltf_exists ? "Present" : "Not yet generated"}
                </span>
              </div>
            )}
            {notCadAcc && (
              <p className="cd-hero-visual-note">Concept placeholder. Not CAD-accurate.</p>
            )}
          </div>
        )}
      </div>

      {/* Dossier panel count summary */}
      {(panels.length > 0 || fallbackCount != null) && (
        <div className="cd-hero-counts">
          <span className="cd-hero-counts-eyebrow">Dossier panels</span>
          <div className="cd-hero-count-row">
            {panels.length > 0 ? (
              <>
                {nAvail   > 0 && (
                  <div className="cd-hero-count-card cd-hero-count-avail">
                    <span className="cd-hero-count-n">{nAvail}</span>
                    <span className="cd-hero-count-lbl">Available</span>
                  </div>
                )}
                {nPlanned > 0 && (
                  <div className="cd-hero-count-card cd-hero-count-planned">
                    <span className="cd-hero-count-n">{nPlanned}</span>
                    <span className="cd-hero-count-lbl">Planned</span>
                  </div>
                )}
                {nMissing > 0 && (
                  <div className="cd-hero-count-card cd-hero-count-missing">
                    <span className="cd-hero-count-n">{nMissing}</span>
                    <span className="cd-hero-count-lbl">Missing</span>
                  </div>
                )}
                {nFailed  > 0 && (
                  <div className="cd-hero-count-card cd-hero-count-failed">
                    <span className="cd-hero-count-n">{nFailed}</span>
                    <span className="cd-hero-count-lbl">Failed</span>
                  </div>
                )}
              </>
            ) : (
              <div className="cd-hero-count-card">
                <span className="cd-hero-count-n">{fallbackCount}</span>
                <span className="cd-hero-count-lbl">Panels</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Allowed visual modes — compact chip row */}
      {allowedModes.length > 0 && (
        <div className="cd-hero-chip-row">
          {allowedModes.slice(0, 5).map((mode, i) => (
            <CdChip key={i} label={mode} variant="mode" />
          ))}
          {allowedModes.length > 5 && (
            <span className="cd-hero-chip-more" aria-label={`${allowedModes.length - 5} more modes`}>
              +{allowedModes.length - 5}
            </span>
          )}
        </div>
      )}

      {/* Safety strip */}
      <div className="cd-hero-safety" role="note">
        <span className="cd-hero-safety-item">Concept-stage dossier</span>
        <span className="cd-hero-safety-item">Presentation preview only</span>
        <span className="cd-hero-safety-item">No engineering validation implied</span>
        <span className="cd-hero-safety-item">Human review required</span>
        {notCadAcc && (
          <span className="cd-hero-safety-item">Not CAD-accurate</span>
        )}
      </div>

    </div>
  );
}

function PanelStatusChip({ status }) {
  const s = typeof status === "string" ? status.toLowerCase() : "";
  const variant =
    s === "available" ? "available" :
    s === "planned"   ? "planned"   :
    s === "missing"   ? "missing"   :
    s === "failed"    ? "failed"    :
    "unknown";
  return (
    <span className={`cd-panel-status cd-panel-status-${variant}`}>
      {typeof status === "string" ? status : "unknown"}
    </span>
  );
}

// ── Dossier panel card ──────────────────────────────────────────────────────

function DossierPanelCard({ panel }) {
  if (!panel || typeof panel !== "object" || Array.isArray(panel)) return null;

  const items         = Array.isArray(panel.items)         ? panel.items         : [];
  const blockedClaims = Array.isArray(panel.blocked_claims) ? panel.blocked_claims : [];
  const brainSummary  = panel.summary && typeof panel.summary === "object" ? panel.summary : null;

  const panelStatusSlug = (typeof panel.status === "string" ? panel.status : "unknown")
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "");

  return (
    <div className={`cd-panel-card cd-panel-card-${panelStatusSlug}`}>
      <div className="cd-panel-card-header">
        <div className="cd-panel-card-title-row">
          <span className="cd-panel-card-title">{panel.title}</span>
          {typeof panel.panel_type === "string" && panel.panel_type && (
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

      {/* items list — label/value pairs, collapsed by default */}
      {items.length > 0 && (
        <details className="p18m-details">
          <summary className="p18m-summary">Dossier panel details</summary>
          <ul className="cd-list">
            {items.map((item, i) => (
              <li key={i} className="cd-list-item">
                {item.label && <span className="cd-list-item-label">{item.label}</span>}
                {item.value ? <span className="cd-list-item-value">{item.value}</span> : null}
              </li>
            ))}
          </ul>
        </details>
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
        <p className="cd-path omni-ds-path">{panel.gltf_preview_path}</p>
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
        <details className="p18m-details">
          <summary className="p18m-summary">Source report paths</summary>
          <p className="cd-path omni-ds-path">{summary.report_path}</p>
        </details>
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
              value={typeof hero.type === "string" && hero.type ? hero.type.replace(/_/g, " ") : "—"}
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

      {/* ── Source reports — collapsed by default ── */}
      {sourceReports.length > 0 && (
        <details className="p18m-details">
          <summary className="p18m-summary">Source report paths</summary>
          <ul className="cd-source-list">
            {sourceReports.map(([key, file]) => (
              <li key={key}>
                <span className="cd-source-key">
                  {key.replace(/_/g, " ")}
                </span>
                <span className="cd-path omni-ds-path">{file}</span>
              </li>
            ))}
          </ul>
        </details>
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
      <div className="cd-panel cd-panel-failed omni-ds-panel omni-ds-theme-dossier">
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
    <div className={`cd-panel${hasManifest ? " cd-panel-available" : " cd-panel-summary"} omni-ds-panel omni-ds-theme-dossier`}>

      {/* ── HUD bar ── */}
      <div className="cd-header">
        <span className="cd-header-label">Concept Dossier</span>
        <div className="cd-header-chips">
          <CdChip label="Concept-stage only" variant="concept" />
          <CdChip label="No engineering validation implied" variant="warn" />
          <CdChip label="Human review required" variant="review" />
        </div>
      </div>

      {/* ── Hero / Reveal ── */}
      <ConceptDossierHero manifest={manifest} summary={summary} />

      {/* ── Persistent safety notice ── */}
      <p className="cd-safety-banner">
        Concept dossier only. No engineering validation implied. No fabrication, flight,
        deployment, or operational readiness implied.
      </p>

      {/* ── Blueprint board ── */}
      {hasManifest && (
        <ConceptDossierBlueprintBoard
          manifest={manifest}
          artifactSummaries={buildArtifactSummaries(exportResult)}
        />
      )}

      {/* ── Content ── */}
      {hasManifest
        ? <RichManifestView manifest={manifest} />
        : <CompactSummaryView summary={summary} />
      }
    </div>
  );
}
