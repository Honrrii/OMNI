// Blueprint/cutaway board foundation for the Concept Dossier experience.
// Presentation contract only. No CAD accuracy, engineering validation,
// fabrication readiness, flight readiness, deployment readiness, or
// simulation verification implied.

// ── Tolerant data helpers ──────────────────────────────────────────────────

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function asObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function safeText(value, fallback) {
  if (value == null) return fallback;
  const s = String(value).trim();
  return s.length > 0 ? s : fallback;
}

function findPanel(manifest, id) {
  const panels = asArray(manifest?.dossier_panels);
  return panels.find(p => p.id === id || p.panel_type === id) || null;
}

// ── Board card derivation ──────────────────────────────────────────────────
// Derives up to 6 board slots from manifest data.
// Prefers actual dossier_panels entries; falls back to allowed_visual_modes
// signals and safe placeholder contracts.

function deriveBoardCards(manifest) {
  const hero = asObject(manifest.hero_visual);
  const allowedModes = asArray(manifest.allowed_visual_modes).map(s =>
    typeof s === "string" ? s.toLowerCase() : ""
  );
  const hasHero = Object.keys(hero).length > 0;
  const modeHas = (kw) => allowedModes.some(m => m.includes(kw));

  // 1 — Concept preview
  const vpPanel = findPanel(manifest, "visual_bay_preview");
  const conceptCard = {
    key:           "concept_preview",
    title:         vpPanel?.title || safeText(hero.label, "Concept Visual Preview"),
    type:          "Concept preview",
    status:        vpPanel?.status || (
      hasHero
        ? (hero.gltf_exists ? "available" : "contract only")
        : "planned"
    ),
    description:   "Visual preview placeholder for concept presentation. No real CAD or render asset.",
    sourceHint:    safeText(vpPanel?.render_hint, null) ||
                   (hero.type ? hero.type.replace(/_/g, " ") : null),
    notCadAccurate: !!(hero.not_cad_accurate),
  };

  // 2 — Blueprint-style summary
  const bpPanel = findPanel(manifest, "blueprint_placeholders");
  const blueprintCard = {
    key:          "blueprint_summary",
    title:        safeText(bpPanel?.title, "Blueprint-style Summary"),
    type:         "Blueprint-style summary",
    status:       bpPanel?.status || (modeHas("blueprint") ? "planned" : "contract only"),
    description:  "Structured layout summary placeholder. Presentation contract only. No engineering drawing implied.",
    sourceHint:   safeText(bpPanel?.render_hint, null),
    notCadAccurate: false,
  };

  // 3 — Cutaway-style explanation
  const cutawayCard = {
    key:          "cutaway_explanation",
    title:        "Cutaway-style Explanation",
    type:         "Cutaway-style explanation",
    status:       modeHas("cutaway") ? "planned" : "contract only",
    description:  "Conceptual cross-section explanation placeholder. No engineering geometry or measured dimensions.",
    sourceHint:   null,
    notCadAccurate: false,
  };

  // 4 — Subsystem callout
  const subsystemCard = {
    key:          "subsystem_callout",
    title:        "Subsystem Callout Panel",
    type:         "Subsystem callout",
    status:       "planned",
    description:  "Abstract subsystem map for visual presentation only. No technical specifications or measured dimensions.",
    sourceHint:   null,
    notCadAccurate: false,
  };

  // 5 — Engineering readiness
  const engPanel = findPanel(manifest, "engineering_brain");
  const engineeringCard = {
    key:          "engineering_readiness",
    title:        safeText(engPanel?.title, "Engineering Readiness Panel"),
    type:         "Engineering readiness",
    status:       engPanel?.status || "contract only",
    description:  "Concept-stage engineering review placeholder. No validation, fabrication readiness, or operational readiness implied.",
    sourceHint:   safeText(engPanel?.render_hint, null),
    notCadAccurate: false,
  };

  // 6 — Safety boundary
  const safetyPanel = findPanel(manifest, "safety_boundary");
  const safetyCard = {
    key:          "safety_boundary",
    title:        safeText(safetyPanel?.title, "Safety Boundary Panel"),
    type:         "Safety boundary",
    status:       safetyPanel?.status || "planned",
    description:  "Safety constraint and boundary visualization placeholder. Human review required.",
    sourceHint:   safeText(safetyPanel?.render_hint, null),
    notCadAccurate: false,
  };

  return [conceptCard, blueprintCard, cutawayCard, subsystemCard, engineeringCard, safetyCard];
}

// ── Blueprint card ─────────────────────────────────────────────────────────

function BlueprintCard({ card }) {
  const statusSlug = (card.status || "planned")
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "");

  return (
    <div className="cd-blueprint-card" role="listitem">
      <div className="cd-blueprint-card-header">
        <div className="cd-blueprint-card-title-col">
          <h4 className="cd-blueprint-card-title">{card.title}</h4>
          <span className="cd-blueprint-type">{card.type}</span>
        </div>
        <span className={`cd-blueprint-status cd-blueprint-status-${statusSlug}`}>
          {card.status}
        </span>
      </div>

      {card.description && (
        <p className="cd-blueprint-description">{card.description}</p>
      )}

      {card.sourceHint && (
        <span className="cd-blueprint-source">{card.sourceHint}</span>
      )}

      {card.notCadAccurate && (
        <div className="cd-blueprint-chip-row">
          <span className="cd-blueprint-chip cd-blueprint-chip-concept">Not CAD-accurate</span>
          <span className="cd-blueprint-chip">Concept placeholder</span>
        </div>
      )}
    </div>
  );
}

// ── Root component ─────────────────────────────────────────────────────────

export default function ConceptDossierBlueprintBoard({ manifest }) {
  if (!manifest) return null;

  const boardCards   = deriveBoardCards(manifest);
  const missionTitle = safeText(manifest.mission_title, null);
  const platform     = safeText(manifest.platform_intent, null);
  const missionType  = safeText(manifest.mission_type, null);
  const conceptOnly  = manifest.concept_stage_only;
  const calloutModes = asArray(manifest.allowed_visual_modes).slice(0, 3);

  const hasCallouts = missionType || conceptOnly || calloutModes.length > 0;

  return (
    <div
      className="cd-blueprint"
      role="region"
      aria-label="Concept blueprint-style board"
    >

      {/* Board header */}
      <div className="cd-blueprint-header">
        <div className="cd-blueprint-kicker">
          <span aria-hidden="true">⬡</span>
          Blueprint Board
        </div>
        <h3 className="cd-blueprint-title">
          {missionTitle
            ? `${missionTitle} — Concept Layout Board`
            : "Concept Layout Board"}
        </h3>
        {platform && <p className="cd-blueprint-platform">{platform}</p>}
      </div>

      {/* Decorative divider rail */}
      <div className="cd-blueprint-rail" aria-hidden="true">
        <div className="cd-blueprint-rail-line" />
        <div className="cd-blueprint-rail-dot" />
        <div className="cd-blueprint-rail-line" />
      </div>

      {/* Board card grid */}
      <div className="cd-blueprint-grid" role="list">
        {boardCards.map(card => (
          <BlueprintCard key={card.key} card={card} />
        ))}
      </div>

      {/* Callouts — mission context chips */}
      {hasCallouts && (
        <div className="cd-blueprint-callouts">
          <span className="cd-blueprint-callouts-label">Board notes</span>
          <div className="cd-blueprint-chip-row">
            {missionType && (
              <span className="cd-blueprint-chip">{missionType}</span>
            )}
            {conceptOnly && (
              <span className="cd-blueprint-chip cd-blueprint-chip-concept">
                Concept-stage only
              </span>
            )}
            {calloutModes.map((m, i) => (
              <span key={i} className="cd-blueprint-chip cd-blueprint-chip-mode">{m}</span>
            ))}
          </div>
        </div>
      )}

      {/* Safety notice */}
      <p className="cd-blueprint-safety">
        Blueprint/cutaway board is a presentation contract only. No CAD accuracy, measured
        dimensions, engineering validation, fabrication readiness, flight readiness, deployment
        readiness, or simulation verification implied.
      </p>

    </div>
  );
}
