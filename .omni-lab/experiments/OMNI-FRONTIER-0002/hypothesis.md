# OMNI-FRONTIER-0002 — Hypothesis

For Component Intelligence v0.1, the choice that matters most is not graph versus typed records versus rules. It is whether every engineering value carries its own epistemic state (KNOWN, UNKNOWN or ASSUMED) and its own provenance, and whether that survives every stage boundary through to CAD. OMNI's current downstream layers cannot carry UNKNOWN or source class, and they quietly replace a missing value with a concrete one. The CAD IR gives every dimension a numeric default. Unregistered component types become a 50x30x15 mm box. Deserialization silently drops fields it doesn't recognize. OMNI has at least four status vocabularies that don't match, and only one includes UNKNOWN, which no code in mission_graph reads. Reliability scoring averages BLOCKED gates into a single confidence number. Provenance marks every agent's output 'llm_generated' and has no classes like STANDARD or MANUFACTURER. So a Component Intelligence layer could correctly produce UNKNOWN or FAIL findings (for example 'bearing speed rating unavailable' or 'bore does not match seat') and still lose them when it plugs into the existing pipeline: they would become plausible geometry and a positive score. Prediction: unless v0.1 makes (a) a value-level Known/Unknown type with provenance and (b) typed CAD obligations the only path into CAD, with a boundary check that rejects defaulted values, the architecture will not fail closed in practice, however good its rule engine is. The CAD layer currently has no mechanical assembly concepts at all, so v0.1 can define this boundary from scratch rather than retrofit it.

## Mechanism

The mission requires that UNKNOWN is never silently turned into PASS. In this repository, missing information is lost at the stage boundaries rather than inside a rule evaluator. There are four ways it happens.

(1) Geometry defaults. MechanicalComponentSpec uses length_mm=0.0 to mean 'use library default'. `_component()` in cad_detail_pass_planner always fills it from `default_dims()`, which returns (50.0, 30.0, 15.0) for any unregistered type. `component_shape()` falls back to 'box'. MountingFeatureSpec and FastenerPatternSpec default to diameter_mm 6.0 and 3.2. A bearing whose bore is unknown, handed to this IR, would therefore become concrete placeholder geometry with no finding.

(2) Schema filtering. `AssemblySpec.from_dict` keeps only keys in `__dataclass_fields__`. Any upstream `status`, `provenance` or `unknown` annotation not already in the dataclass is silently discarded.

(3) Status collapse. The vocabularies are:
- reliability: PASS/WARN/FAIL/BLOCKED, with no UNKNOWN
- mission_graph ValidationCheck: PASS/WARNING/FAIL/UNKNOWN, but UNKNOWN has no reader in mission_graph
- engineering validation_engine: lowercase pass/warning/blocked
- findings_projection: severities only, where an empty severity becomes 'warning' and status is always 'open'

`compute_engineering_confidence` averages BLOCKED at 0.1 alongside PASS at 1.0, so enough passing gates can outweigh an unknown in the single confidence number.

(4) Provenance flattening. ProvenanceRef.evidence_type defaults to 'llm_generated', and reliability/provenance.py maps all nine agents to 'llm_generated'. EvidenceRecord.confidence is low/medium/high with no source-class axis. Nothing can tell a STANDARD fact from an OMNI_HEURISTIC or AI assertion, so Claude and Codex agreeing cannot be kept separate from validated knowledge.

Architectural consequence (a proposal, not a fact): the core data model should be built around a Fact/Quantity type, roughly {value | UNKNOWN, unit, source_class ∈ {STANDARD, MANUFACTURER, HANDBOOK, OMNI_VALIDATED, OMNI_HEURISTIC, USER_PROVIDED}, source_ref, fact_id}. Typed interfaces, rules, patterns and obligations would all operate on that type. Rule outcomes would use a three-valued logic: any UNKNOWN input yields UNKNOWN unless the rule explicitly declares a justified WARN. Oli would receive a CadObligation set instead of a spec full of defaults. There is a counterweight in the repo: calculation_engine already fails closed (missing_inputs → blocked). Fail-closed behaviour exists locally, but no contract carries it across boundaries.

Informal FrontierResearchScore, not authoritative:
- alignment 5
- impact 5
- information gain 4
- generalizability 5 (applies to every future component family)
- novelty 3
- experimentability 5 (cheap fault injection or property test)
- risk 1
- implementation cost 2

## Competing hypotheses

- The primary architectural risk is incomplete assembly semantics: OMNI can omit a required relationship or select an inappropriate assembly configuration while every represented value is KNOWN and preserves its provenance. Value-level epistemic typing cannot detect a requirement that was never instantiated. I propose making a configuration-specific assembly constraint model the core of v0.1, with fact provenance supporting that model. This competes with the claim that value-state preservation is the decisive architectural choice.
