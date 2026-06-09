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

function asStringArray(value) {
  return Array.isArray(value) ? value.filter(v => typeof v === "string") : [];
}

function firstFileMatch(files, pattern) {
  if (typeof pattern === "string") return files.find(p => p.includes(pattern)) || null;
  if (pattern instanceof RegExp)   return files.find(p => pattern.test(p))    || null;
  return null;
}

function safeText(value, fallback) {
  if (value == null) return fallback;
  const s = String(value).trim();
  return s.length > 0 ? s : fallback;
}

// Create a single evidence row. Returns null when value is absent so callers
// can filter with .filter(Boolean).
function ev(label, value) {
  if (value == null) return null;
  const s = String(value).trim();
  return s.length > 0 ? { label, value: s } : null;
}

function normalizeSlug(value, fallback) {
  return (typeof value === "string" ? value : (fallback || "unknown"))
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "");
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
// detect(sums) returns { status, detail, nuance, reason, evidence, nextAction }.
// Status is limited to "available" | "missing" | "unknown". Never lies.
// sums.files is pre-normalized to string-only by deriveArtifactCards.

const ARTIFACT_CATALOG = [
  // 1 ── Fusion 360 Generator ────────────────────────────────────────────────
  {
    key:      "fusion360",
    name:     "Fusion 360 Generator",
    category: "CAD",
    purpose:  "Python script for parametric Fusion 360 model scaffold",
    detect(sums) {
      const f = asObject(sums.fusion360);
      if (!sums.fusion360) return {
        status: "unknown", detail: null, nuance: null,
        reason: "No Fusion 360 generation summary available.",
        evidence: [], nextAction: null,
      };
      const fileCount = Array.isArray(f.files) ? f.files.length : (f.file_count ?? null);
      const gate = asObject(f.morphology_gate || f.knowledge_gate);
      if (f.status === "generated") return {
        status:  "available",
        detail:  safeText(f.project_type || f.model_name, null),
        nuance:  "concept CAD script",
        reason:  "Fusion 360 script was generated for this mission.",
        evidence: [
          ev("Status",               f.status),
          ev("Project type",         f.project_type),
          ev("Model name",           f.model_name),
          ev("Files",                fileCount),
          ev("Morphology gate",      gate.status),
          ev("Assembly components",  f.assembly_component_count),
        ].filter(Boolean),
        nextAction: "Review Fusion 360 script and parameters before CAD execution or downstream engineering use.",
      };
      if (f.status === "failed") return {
        status: "missing", detail: "Generation failed", nuance: null,
        reason: "Fusion 360 script generation failed.",
        evidence: [ev("Status", f.status)].filter(Boolean), nextAction: null,
      };
      if (f.status === "not_generated") return {
        status: "missing", detail: "No CAD signals detected", nuance: null,
        reason: "No CAD-relevant signals were detected in the mission.",
        evidence: [ev("Status", f.status)].filter(Boolean), nextAction: null,
      };
      return {
        status: "unknown", detail: safeText(f.status, null), nuance: null,
        reason: "Fusion 360 generation status is unclear.",
        evidence: [ev("Status", f.status)].filter(Boolean), nextAction: null,
      };
    },
  },

  // 2 ── CAD README ──────────────────────────────────────────────────────────
  {
    key:      "cad_readme",
    name:     "CAD README",
    category: "CAD",
    purpose:  "Human-readable setup and usage notes for generated CAD scripts",
    detect(sums) {
      const readmePath = firstFileMatch(sums.files, /generated_fusion360.*readme/i);
      if (readmePath) return {
        status: "available", detail: null, nuance: "generated",
        reason: "CAD README file was found in the Fusion 360 export folder.",
        evidence: [ev("File", readmePath)].filter(Boolean),
        nextAction: "Read setup/usage notes before opening CAD assets.",
      };
      const f = asObject(sums.fusion360);
      if (f.status === "failed" || f.status === "not_generated") return {
        status: "missing", detail: "No Fusion 360 export", nuance: null,
        reason: "No Fusion 360 export was generated, so no CAD README exists.",
        evidence: [ev("Fusion 360 status", f.status)].filter(Boolean), nextAction: null,
      };
      if (sums.fusion360) return {
        status: "unknown", detail: null, nuance: null,
        reason: "Fusion 360 script was generated but no CAD README file was found in the files list.",
        evidence: [ev("Fusion 360 status", f.status)].filter(Boolean),
        nextAction: "Read setup/usage notes before opening CAD assets.",
      };
      return {
        status: "unknown", detail: null, nuance: null,
        reason: "No Fusion 360 summary or file evidence available.",
        evidence: [], nextAction: null,
      };
    },
  },

  // 3 ── Assembly Spec ───────────────────────────────────────────────────────
  {
    key:      "assembly_spec",
    name:     "Assembly Spec",
    category: "CAD",
    purpose:  "Component hierarchy and assembly intent for the physical structure",
    detect(sums) {
      const asmFile = firstFileMatch(sums.files, "component_tree") ||
                      firstFileMatch(sums.files, /assembly/i);
      const f = asObject(sums.fusion360);
      const asmAvail = f.assembly_detail_available;
      const asmCount = f.assembly_component_count ?? null;
      const asmLevel = f.assembly_detail_level ?? null;
      const asmVis   = f.assembly_visibility_mode ?? null;
      const hasAsmFields = asmCount != null || asmLevel != null || asmVis != null;

      if (asmFile) return {
        status: "available", detail: "Component tree", nuance: "generated",
        reason: "Assembly/component tree file was found in the export.",
        evidence: [
          ev("File",        asmFile),
          ev("Components",  asmCount),
          ev("Detail level", asmLevel),
          ev("Visibility",  asmVis),
        ].filter(Boolean),
        nextAction: "Inspect component hierarchy and placeholder geometry assumptions.",
      };
      if (hasAsmFields && asmAvail !== false) return {
        status: "available",
        detail: asmCount != null ? `${asmCount} components` : null,
        nuance: "generated",
        reason: "Assembly spec is present based on Fusion 360 assembly fields.",
        evidence: [
          ev("Assembly available", asmAvail != null ? String(asmAvail) : null),
          ev("Components",         asmCount),
          ev("Detail level",       asmLevel),
          ev("Visibility",         asmVis),
        ].filter(Boolean),
        nextAction: "Inspect component hierarchy and placeholder geometry assumptions.",
      };
      if (sums.files.length > 0) return {
        status: "missing", detail: null, nuance: null,
        reason: "No assembly or component tree file found in the export.",
        evidence: [], nextAction: null,
      };
      return {
        status: "unknown", detail: null, nuance: null,
        reason: "Insufficient evidence to determine assembly spec availability.",
        evidence: [], nextAction: null,
      };
    },
  },

  // 4 ── Morphology Spec ─────────────────────────────────────────────────────
  {
    key:      "morphology_spec",
    name:     "Morphology Spec",
    category: "Architecture",
    purpose:  "Body plan, segment layout, and electronics intent for the mission platform",
    detect(sums) {
      const morphFile = firstFileMatch(sums.files, "morphology_plan") ||
                        firstFileMatch(sums.files, "morphology_spec");
      if (morphFile) return {
        status: "available", detail: null, nuance: "generated",
        reason: "Morphology plan file was found in the export.",
        evidence: [ev("File", morphFile)].filter(Boolean),
        nextAction: "Verify body plan and subsystem placement before CAD refinement.",
      };
      const m = asObject(sums.morphology);
      const morphId = m.morphology_id || m.identity?.morphology_id || null;
      if (morphId) return {
        status: "available", detail: safeText(morphId, null), nuance: "generated",
        reason: "Morphology identity is confirmed in the export summary.",
        evidence: [ev("Morphology ID", morphId)].filter(Boolean),
        nextAction: "Verify body plan and subsystem placement before CAD refinement.",
      };
      return {
        status: "unknown", detail: null, nuance: null,
        reason: "No morphology plan file or explicit identity field found.",
        evidence: [], nextAction: null,
      };
    },
  },

  // 5 ── Morphology Quality Report ───────────────────────────────────────────
  {
    key:      "morphology_quality",
    name:     "Morphology Quality Report",
    category: "Architecture",
    purpose:  "Gate validation checking morphology consistency across generated artifacts",
    detect(sums) {
      if (!sums.morphology) return {
        status: "unknown", detail: null, nuance: null,
        reason: "No morphology validation summary available.",
        evidence: [], nextAction: null,
      };
      const m = asObject(sums.morphology);
      const summary   = asObject(m.summary);
      const blockers  = summary.blockers    ?? null;
      const warnings  = summary.warnings    ?? null;
      const total     = summary.total_issues ?? null;
      const score     = m.score             ?? null;
      let nuance, reason, detail;
      if (m.status === "passed" || m.status === "reviewed") {
        nuance = "gate passed"; reason = "Morphology gate validation passed.";
        detail = "Gate passed";
      } else if (m.status === "failed") {
        nuance = "gate failed";
        reason = `Morphology gate failed with ${blockers ?? "?"} blocker(s).`;
        detail = `Gate failed — ${total ?? "?"} issues`;
      } else {
        nuance = "unknown"; reason = `Morphology report status: ${m.status || "unknown"}.`;
        detail = safeText(m.status, null);
      }
      return {
        status: "available", detail, nuance, reason,
        evidence: [
          ev("Status",       m.status),
          ev("Blockers",     blockers),
          ev("Warnings",     warnings),
          ev("Total issues", total),
          ev("Score",        score),
        ].filter(Boolean),
        nextAction: "Resolve blockers/warnings before making engineering readiness claims.",
      };
    },
  },

  // 6 ── Concept Dossier ─────────────────────────────────────────────────────
  {
    key:      "concept_dossier",
    name:     "Concept Dossier",
    category: "Dossier",
    purpose:  "Mission presentation manifest with dossier panels and engineering summary",
    detect(sums) {
      if (!sums.concept_dossier) return {
        status: "unknown", detail: null, nuance: null,
        reason: "No concept dossier summary available.",
        evidence: [], nextAction: null,
      };
      const cd = asObject(sums.concept_dossier);
      if (cd.status === "generated" || cd.status === "available") return {
        status:  "available",
        detail:  cd.panel_count != null ? `${cd.panel_count} panels` : null,
        nuance:  "generated",
        reason:  "Concept dossier manifest was generated for this mission.",
        evidence: [
          ev("Status",      cd.status),
          ev("Panels",      cd.panel_count),
          ev("Schema",      cd.schema),
          ev("Report path", cd.report_path),
        ].filter(Boolean),
        nextAction: "Review generated mission narrative and blocked claims.",
      };
      if (cd.status === "failed") return {
        status: "missing", detail: "Export failed", nuance: null,
        reason: "Concept dossier export failed.",
        evidence: [ev("Status", cd.status)].filter(Boolean), nextAction: null,
      };
      return {
        status: "unknown", detail: safeText(cd.status, null), nuance: null,
        reason: "Concept dossier status is unclear.",
        evidence: [ev("Status", cd.status)].filter(Boolean), nextAction: null,
      };
    },
  },

  // 7 ── Critique ────────────────────────────────────────────────────────────
  {
    key:      "critique",
    name:     "Critique",
    category: "Review",
    purpose:  "Agent critique of the mission plan and proposed design",
    detect(sums) {
      const critFile = sums.files.find(
        p => p === "critique.json" || p.endsWith("/critique.json")
      ) || null;
      if (critFile) return {
        status: "available", detail: null, nuance: "generated",
        reason: "Critique artifact file was found in the export. Critique content quality is not evaluated here.",
        evidence: [ev("File", critFile)].filter(Boolean),
        nextAction: "Review critique findings before continuing the design.",
      };
      if (sums.files.length > 0) return {
        status: "missing", detail: null, nuance: null,
        reason: "Critique file was not found in the export file list.",
        evidence: [], nextAction: null,
      };
      return {
        status: "unknown", detail: null, nuance: null,
        reason: "No export file list available to verify critique artifact.",
        evidence: [], nextAction: null,
      };
    },
  },

  // 8 ── Candidate Evaluation ────────────────────────────────────────────────
  {
    key:      "candidate_evaluation",
    name:     "Candidate Evaluation",
    category: "Review",
    purpose:  "Ranked evaluation of design candidates with recommended design ID",
    detect(sums) {
      if (!sums.candidate_evaluation) return {
        status: "unknown", detail: null, nuance: null,
        reason: "No candidate evaluation summary available.",
        evidence: [], nextAction: null,
      };
      const ce = asObject(sums.candidate_evaluation);
      if (ce.status === "evaluated") return {
        status:  "available",
        detail:  ce.candidates_evaluated != null ? `${ce.candidates_evaluated} candidates` : null,
        nuance:  "generated",
        reason:  "Design candidates were evaluated and ranked.",
        evidence: [
          ev("Status",             ce.status),
          ev("Candidates",         ce.candidates_evaluated),
          ev("Recommended ID",     ce.recommended_candidate_id),
          ev("Report path",        ce.report_path),
        ].filter(Boolean),
        nextAction: "Compare candidate ranking against mission constraints.",
      };
      if (ce.status === "skipped") return {
        status: "missing", detail: "No candidates available", nuance: null,
        reason: "No design candidates were available for evaluation.",
        evidence: [ev("Status", ce.status)].filter(Boolean), nextAction: null,
      };
      if (ce.status === "failed") return {
        status: "missing", detail: "Evaluation failed", nuance: null,
        reason: "Candidate evaluation failed.",
        evidence: [ev("Status", ce.status)].filter(Boolean), nextAction: null,
      };
      return {
        status: "unknown", detail: safeText(ce.status, null), nuance: null,
        reason: "Candidate evaluation status is unclear.",
        evidence: [ev("Status", ce.status)].filter(Boolean), nextAction: null,
      };
    },
  },

  // 9 ── Generated KiCad ─────────────────────────────────────────────────────
  {
    key:      "kicad",
    name:     "Generated KiCad",
    category: "Electronics",
    purpose:  "Starter KiCad electronics package with BOM, schematic scaffold, and knowledge context",
    detect(sums) {
      if (!sums.kicad) return {
        status: "unknown", detail: null, nuance: null,
        reason: "No KiCad generation summary available.",
        evidence: [], nextAction: null,
      };
      const k    = asObject(sums.kicad);
      const gate = asObject(k.knowledge_gate);
      const gs   = asObject(gate.summary);
      const fileCount = Array.isArray(k.files) ? k.files.length : (k.file_count ?? null);
      if (k.status === "generated") {
        let nuance;
        if      (gate.status === "passed_with_warnings") nuance = "passed with warnings";
        else if (gate.status === "passed")               nuance = "gate passed";
        else if (gate.status === "failed")               nuance = "gate failed";
        else if (gate.status)                            nuance = "starter package";
        else                                             nuance = "generated";
        return {
          status:  "available",
          detail:  safeText(k.package_type, null),
          nuance,
          reason:  "KiCad electronics package was generated.",
          evidence: [
            ev("Package type",    k.package_type),
            ev("Files",           fileCount),
            ev("Knowledge gate",  gate.status),
            ev("Gate warnings",   gs.warnings),
          ].filter(Boolean),
          nextAction: "Complete ERC/DRC, footprints, routing, Gerbers/drill files, and manufacturing review before PCB use.",
        };
      }
      if (k.status === "failed") return {
        status: "missing", detail: "Generation failed", nuance: null,
        reason: "KiCad package generation failed.",
        evidence: [ev("Status", k.status)].filter(Boolean), nextAction: null,
      };
      if (k.status === "not_generated") return {
        status: "missing", detail: "No electronics signals detected", nuance: null,
        reason: "No electronics-relevant signals were detected in the mission.",
        evidence: [ev("Status", k.status)].filter(Boolean), nextAction: null,
      };
      return {
        status: "unknown", detail: safeText(k.status, null), nuance: null,
        reason: "KiCad generation status is unclear.",
        evidence: [ev("Status", k.status)].filter(Boolean), nextAction: null,
      };
    },
  },

  // 10 ── Generated ROS2 ─────────────────────────────────────────────────────
  {
    key:      "ros2",
    name:     "Generated ROS2",
    category: "Software",
    purpose:  "Starter ROS2 package scaffold with node graph, launch files, and build config",
    detect(sums) {
      if (!sums.ros2) return {
        status: "unknown", detail: null, nuance: null,
        reason: "No ROS2 generation summary available.",
        evidence: [], nextAction: null,
      };
      const r         = asObject(sums.ros2);
      const fileCount = Array.isArray(r.files) ? r.files.length : (r.file_count ?? null);
      const val       = asObject(sums.ros2_validation);
      if (r.status === "generated") return {
        status:  "available",
        detail:  safeText(r.package_name, null),
        nuance:  "starter package",
        reason:  "ROS2 package scaffold was generated.",
        evidence: [
          ev("Package name",       r.package_name),
          ev("Files",              fileCount),
          ev("ROS2 check status",  val.status),
          ev("ROS2 checks passed", val.passed != null ? String(val.passed) : null),
        ].filter(Boolean),
        nextAction: "Run colcon build, topic smoke tests, and hardware review.",
      };
      if (r.status === "failed") return {
        status: "missing", detail: "Generation failed", nuance: null,
        reason: "ROS2 package generation failed.",
        evidence: [ev("Status", r.status)].filter(Boolean), nextAction: null,
      };
      if (r.status === "not_generated") return {
        status: "missing", detail: "No ROS2 signals detected", nuance: null,
        reason: "No ROS2-relevant signals were detected in the mission.",
        evidence: [ev("Status", r.status)].filter(Boolean), nextAction: null,
      };
      return {
        status: "unknown", detail: safeText(r.status, null), nuance: null,
        reason: "ROS2 generation status is unclear.",
        evidence: [ev("Status", r.status)].filter(Boolean), nextAction: null,
      };
    },
  },

  // 11 ── Generated Visuals ──────────────────────────────────────────────────
  {
    key:      "visuals",
    name:     "Generated Visuals",
    category: "Visual",
    purpose:  "Visual Bay preview assets including GLTF scene and browser-ready renders",
    detect(sums) {
      if (!sums.visual_bay) return {
        status: "unknown", detail: null, nuance: null,
        reason: "No Visual Bay summary available.",
        evidence: [], nextAction: null,
      };
      const vb = asObject(sums.visual_bay);
      if (vb.status === "failed") return {
        status: "missing", detail: "Visual Bay failed", nuance: null,
        reason: "Visual Bay generation failed.",
        evidence: [ev("Status", vb.status)].filter(Boolean), nextAction: null,
      };
      if (vb.status === "empty") return {
        status: "missing", detail: "No visual assets", nuance: null,
        reason: "No visual preview assets were found.",
        evidence: [ev("Status", vb.status)].filter(Boolean), nextAction: null,
      };
      // Default to preview-only unless payload explicitly proves otherwise.
      const previewOnly = vb.preview_only !== false;
      const meshAvail   = vb.mesh_available ?? null;
      const browserOk   = !!vb.browser_preview_ready;
      const count       = vb.browser_preview_ready_count ?? vb.preview_asset_count ?? null;
      const gltfPath    = firstFileMatch(sums.files, /preview_scene\.gltf/i) ||
                          (browserOk ? "generated_visual_bay/preview_scene.gltf" : null);
      const hasVisuals  = vb.has_cad || browserOk || vb.has_ros2 || vb.has_simulation_assets;
      // Shared evidence builder for available states.
      const sharedEvidence = [
        ev("Status",                   vb.status),
        ev("Preview assets",           vb.preview_asset_count),
        ev("Browser-ready assets",     vb.browser_preview_ready_count),
        ev("Engineering-only assets",  vb.engineering_only_count),
        ev("Execution-blocked assets", vb.execution_blocked_count),
        ev("Browser preview",          String(browserOk)),
        ev("Safe to launch",           vb.safe_to_launch != null ? String(vb.safe_to_launch) : null),
        ev("GLTF scene",               gltfPath),
        ev("CAD source detected",      vb.has_cad != null ? String(vb.has_cad) : null),
        ev("Has ROS2",                 vb.has_ros2 != null ? String(vb.has_ros2) : null),
        // Only include mesh_available when the field exists in the payload.
        meshAvail != null ? ev("Mesh available", String(meshAvail)) : null,
      ].filter(Boolean);
      const notCadReason = "This output is a visual preview and is not engineering CAD or mesh.";
      if (vb.status === "partial") return {
        status: "available",
        detail: count != null ? `${count} preview assets` : "Partial visual assets",
        nuance: "preview only",
        reason: `Visual Bay has partial assets. Not all visual asset types are present. ${notCadReason}`,
        evidence: sharedEvidence,
        nextAction: "Use preview for visual inspection only; do not treat it as engineering CAD.",
      };
      if (hasVisuals || vb.status === "available" || vb.status === "generated" || vb.status === "ok") {
        const reason = previewOnly || meshAvail !== true
          ? `Visual Bay preview assets are available. ${notCadReason}`
          : "Visual Bay preview assets are available.";
        return {
          status:  "available",
          detail:  count != null ? `${count} preview assets` : null,
          nuance:  "preview only",
          reason,
          evidence: sharedEvidence,
          nextAction: "Use preview for visual inspection only; do not treat it as engineering CAD.",
        };
      }
      return {
        status: "unknown", detail: null, nuance: null,
        reason: "Visual Bay status is present but visual availability is unclear.",
        evidence: [ev("Status", vb.status)].filter(Boolean), nextAction: null,
      };
    },
  },
];

const VALID_STATUSES = new Set(["available", "missing", "unknown"]);

function deriveArtifactCards(manifest, artifactSummaries) {
  const raw  = artifactSummaries && typeof artifactSummaries === "object"
    ? artifactSummaries : {};
  const sums = { ...raw, files: asStringArray(raw.files) };

  return ARTIFACT_CATALOG.map(entry => {
    let status     = "unknown";
    let detail     = null;
    let nuance     = null;
    let reason     = null;
    let evidence   = [];
    let nextAction = null;
    try {
      const result   = entry.detect(sums);
      const rawSlug  = normalizeSlug(result?.status, "unknown");
      status         = VALID_STATUSES.has(rawSlug) ? rawSlug : "unknown";
      detail     = result?.detail     ?? null;
      nuance     = result?.nuance     ?? null;
      reason     = result?.reason     ?? null;
      evidence   = Array.isArray(result?.evidence) ? result.evidence : [];
      nextAction = result?.nextAction ?? null;
    } catch { /* keep defaults */ }
    return {
      key:       entry.key,
      name:      entry.name,
      category:  entry.category,
      purpose:   entry.purpose,
      status, detail, nuance, reason, evidence, nextAction,
    };
  });
}

// ── Blueprint card ─────────────────────────────────────────────────────────

function BlueprintCard({ card }) {
  const statusSlug = normalizeSlug(card.status, "planned");
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
  const evidenceRows = Array.isArray(artifact.evidence) ? artifact.evidence : [];
  const hasDrilldown = !!(artifact.nuance || artifact.reason || evidenceRows.length > 0 || artifact.nextAction);
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
      {hasDrilldown && (
        <details className="cd-blueprint-artifact-drilldown">
          <summary className="cd-blueprint-artifact-drilldown-summary">
            {artifact.nuance || "details"}
          </summary>
          <div className="cd-blueprint-artifact-drilldown-body">
            {artifact.reason && (
              <p className="cd-blueprint-artifact-drilldown-reason">{artifact.reason}</p>
            )}
            {evidenceRows.length > 0 && (
              <dl className="cd-blueprint-artifact-evidence">
                {evidenceRows.map((row, i) => (
                  <div key={i} className="cd-blueprint-artifact-evidence-row">
                    <dt className="cd-blueprint-artifact-evidence-k">{row.label}</dt>
                    <dd className="cd-blueprint-artifact-evidence-v">{row.value}</dd>
                  </div>
                ))}
              </dl>
            )}
            {artifact.nextAction && (
              <p className="cd-blueprint-artifact-next-action">{artifact.nextAction}</p>
            )}
          </div>
        </details>
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
