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
  return panels.find(
    p => p && typeof p === "object" && !Array.isArray(p) &&
         (p.id === id || p.panel_type === id)
  ) || null;
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

// ── Artifact intelligence catalog ──────────────────────────────────────────
// Each entry has a detect(sums) function that reads compact export summaries
// and the files list. Returns { status, detail } where status is one of
// "available" | "missing" | "unknown". Never lies: if uncertain → "unknown".

const ARTIFACT_CATALOG = [
  {
    key:      "fusion360",
    name:     "Fusion 360 Generator",
    category: "CAD",
    purpose:  "Python script for parametric Fusion 360 model scaffold",
    detect(sums) {
      const f = sums.fusion360;
      if (!f) return { status: "unknown", detail: null };
      if (f.status === "generated") return {
        status: "available",
        detail: safeText(f.project_type || f.model_name, null),
      };
      if (f.status === "failed")        return { status: "missing", detail: "Generation failed" };
      if (f.status === "not_generated") return { status: "missing", detail: "No CAD signals detected" };
      return { status: "unknown", detail: safeText(f.status, null) };
    },
  },
  {
    key:      "cad_readme",
    name:     "CAD README",
    category: "CAD",
    purpose:  "Human-readable setup and usage notes for generated CAD scripts",
    detect(sums) {
      if (sums.fusion360?.status === "generated") return { status: "available", detail: "In fusion360 export folder" };
      if (sums.files.some(p => typeof p === "string" && /generated_fusion360.*readme/i.test(p))) {
        return { status: "available", detail: null };
      }
      if (sums.fusion360?.status === "failed" || sums.fusion360?.status === "not_generated") {
        return { status: "missing", detail: "No Fusion 360 export" };
      }
      return { status: "unknown", detail: null };
    },
  },
  {
    key:      "assembly_spec",
    name:     "Assembly Spec",
    category: "CAD",
    purpose:  "Component hierarchy and assembly intent for the physical structure",
    detect(sums) {
      if (sums.files.some(p => typeof p === "string" && p.includes("component_tree"))) {
        return { status: "available", detail: "Component tree" };
      }
      if (sums.files.some(p => typeof p === "string" && /assembly/i.test(p))) {
        return { status: "available", detail: null };
      }
      if (sums.files.length > 0) return { status: "missing", detail: null };
      return { status: "unknown", detail: null };
    },
  },
  {
    key:      "morphology_spec",
    name:     "Morphology Spec",
    category: "Architecture",
    purpose:  "Body plan, segment layout, and electronics intent for the mission platform",
    detect(sums) {
      if (sums.files.some(p => typeof p === "string" && p.includes("morphology_plan"))) {
        return { status: "available", detail: null };
      }
      const morphId = sums.morphology?.morphology_id || sums.morphology?.identity?.morphology_id;
      if (morphId) return { status: "available", detail: safeText(morphId, null) };
      return { status: "unknown", detail: null };
    },
  },
  {
    key:      "morphology_quality",
    name:     "Morphology Quality Report",
    category: "Architecture",
    purpose:  "Gate validation checking morphology consistency across generated artifacts",
    detect(sums) {
      const m = sums.morphology;
      if (!m) return { status: "unknown", detail: null };
      if (m.status === "passed" || m.status === "reviewed") return { status: "available", detail: "Gate passed" };
      if (m.status === "failed") {
        const n = m.summary?.total_issues;
        return { status: "available", detail: `Gate failed — ${n != null ? n : "?"} issues` };
      }
      if (m.status) return { status: "available", detail: safeText(m.status, null) };
      return { status: "unknown", detail: null };
    },
  },
  {
    key:      "concept_dossier",
    name:     "Concept Dossier",
    category: "Dossier",
    purpose:  "Mission presentation manifest with dossier panels and engineering summary",
    detect(sums) {
      const cd = sums.concept_dossier;
      if (!cd) return { status: "unknown", detail: null };
      if (cd.status === "generated" || cd.status === "available") {
        return { status: "available", detail: cd.panel_count != null ? `${cd.panel_count} panels` : null };
      }
      if (cd.status === "failed") return { status: "missing", detail: "Export failed" };
      return { status: "unknown", detail: safeText(cd.status, null) };
    },
  },
  {
    key:      "critique",
    name:     "Critique",
    category: "Review",
    purpose:  "Agent critique of the mission plan and proposed design",
    detect(sums) {
      if (sums.files.some(p => typeof p === "string" && (p === "critique.json" || p.endsWith("/critique.json")))) {
        return { status: "available", detail: null };
      }
      if (sums.files.length > 0) return { status: "missing", detail: null };
      return { status: "unknown", detail: null };
    },
  },
  {
    key:      "candidate_evaluation",
    name:     "Candidate Evaluation",
    category: "Review",
    purpose:  "Ranked evaluation of design candidates with recommended design ID",
    detect(sums) {
      const ce = sums.candidate_evaluation;
      if (!ce) return { status: "unknown", detail: null };
      if (ce.status === "evaluated") {
        return { status: "available", detail: ce.candidates_evaluated != null ? `${ce.candidates_evaluated} candidates` : null };
      }
      if (ce.status === "skipped") return { status: "missing", detail: "No candidates available" };
      if (ce.status === "failed")  return { status: "missing", detail: "Evaluation failed" };
      return { status: "unknown", detail: safeText(ce.status, null) };
    },
  },
  {
    key:      "kicad",
    name:     "Generated KiCad",
    category: "Electronics",
    purpose:  "Starter KiCad electronics package with BOM, schematic scaffold, and knowledge context",
    detect(sums) {
      const k = sums.kicad;
      if (!k) return { status: "unknown", detail: null };
      if (k.status === "generated")     return { status: "available", detail: safeText(k.package_type, null) };
      if (k.status === "failed")        return { status: "missing",   detail: "Generation failed" };
      if (k.status === "not_generated") return { status: "missing",   detail: "No electronics signals detected" };
      return { status: "unknown", detail: safeText(k.status, null) };
    },
  },
  {
    key:      "ros2",
    name:     "Generated ROS2",
    category: "Software",
    purpose:  "Starter ROS2 package scaffold with node graph, launch files, and build config",
    detect(sums) {
      const r = sums.ros2;
      if (!r) return { status: "unknown", detail: null };
      if (r.status === "generated")     return { status: "available", detail: safeText(r.package_name, null) };
      if (r.status === "failed")        return { status: "missing",   detail: "Generation failed" };
      if (r.status === "not_generated") return { status: "missing",   detail: "No ROS2 signals detected" };
      return { status: "unknown", detail: safeText(r.status, null) };
    },
  },
  {
    key:      "visuals",
    name:     "Generated Visuals",
    category: "Visual",
    purpose:  "Visual Bay preview assets including GLTF scene and browser-ready renders",
    detect(sums) {
      const vb = sums.visual_bay;
      if (!vb) return { status: "unknown", detail: null };
      if (vb.status === "failed") return { status: "missing", detail: "Visual Bay failed" };
      if (vb.status === "empty")  return { status: "missing", detail: "No visual assets" };
      const count = vb.browser_preview_ready_count ?? vb.preview_asset_count ?? null;
      if (vb.status === "partial") {
        return { status: "available", detail: count != null ? `${count} preview assets` : "Partial visual assets" };
      }
      if (vb.has_cad || vb.browser_preview_ready || vb.has_ros2 || vb.has_simulation_assets) {
        return { status: "available", detail: count != null ? `${count} preview assets` : null };
      }
      if (vb.status === "generated" || vb.status === "ok") {
        return { status: "available", detail: count != null ? `${count} preview assets` : null };
      }
      return { status: "unknown", detail: null };
    },
  },
];

function deriveArtifactCards(manifest, artifactSummaries) {
  const sums = artifactSummaries && typeof artifactSummaries === "object"
    ? { files: [], ...artifactSummaries }
    : { files: [] };

  return ARTIFACT_CATALOG.map(entry => {
    let status = "unknown";
    let detail = null;
    try {
      const result = entry.detect(sums);
      status = typeof result?.status === "string"
        ? result.status.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "")
        : "unknown";
      detail = result?.detail ?? null;
    } catch { /* keep unknown */ }
    return {
      key:      entry.key,
      name:     entry.name,
      category: entry.category,
      purpose:  entry.purpose,
      status,
      detail,
    };
  });
}

// ── Blueprint card ─────────────────────────────────────────────────────────

function BlueprintCard({ card }) {
  const statusSlug = (typeof card.status === "string" ? card.status : "planned")
    .toLowerCase()
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
          {typeof card.status === "string" ? card.status : "planned"}
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

// ── Artifact card ──────────────────────────────────────────────────────────

function ArtifactCard({ artifact }) {
  return (
    <div className="cd-blueprint-artifact" role="listitem">
      <div className="cd-blueprint-artifact-header">
        <div className="cd-blueprint-artifact-title-col">
          <span className="cd-blueprint-artifact-name">{artifact.name}</span>
          <span className="cd-blueprint-artifact-cat">{artifact.category}</span>
        </div>
        <span className={`cd-blueprint-artifact-status cd-blueprint-artifact-status-${artifact.status}`}>
          {artifact.status}
        </span>
      </div>
      <p className="cd-blueprint-artifact-purpose">{artifact.purpose}</p>
      {artifact.detail && (
        <span className="cd-blueprint-artifact-detail">{artifact.detail}</span>
      )}
    </div>
  );
}

// ── Root component ─────────────────────────────────────────────────────────

export default function ConceptDossierBlueprintBoard({ manifest, artifactSummaries }) {
  if (!manifest) return null;

  const boardCards    = deriveBoardCards(manifest);
  const artifactCards = deriveArtifactCards(manifest, artifactSummaries);
  const missionTitle  = safeText(manifest.mission_title, null);
  const platform      = safeText(manifest.platform_intent, null);
  const missionType   = safeText(manifest.mission_type, null);
  const conceptOnly   = manifest.concept_stage_only;
  const calloutModes  = asArray(manifest.allowed_visual_modes).slice(0, 3);

  const hasCallouts  = missionType || conceptOnly || calloutModes.length > 0;

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

      {/* Artifact intelligence section */}
      {artifactCards.length > 0 && (
        <div className="cd-blueprint-artifact-section">
          <div className="cd-blueprint-artifact-heading">
            <span aria-hidden="true">⬢</span>
            Artifact Intelligence
          </div>
          <div className="cd-blueprint-artifact-grid" role="list">
            {artifactCards.map(a => (
              <ArtifactCard key={a.key} artifact={a} />
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
