# OMNI-FRONTIER-0003 — Hypothesis

For Component Intelligence v0.1, the most important choice is how a verdict gets computed. The storage format (graph, typed records or rules) matters less. The system should list every obligation an assembly must meet, derived from component types, and grade each one. It should not just collect whatever defects its detectors happen to find. A pairwise compatibility-rule engine running over an interface graph cannot see a relationship that is missing. If a rotating shaft has no shaft_to_bearing edge, no rule fires, no finding appears, and the result defaults to PASS. Every validator and graph pattern OMNI uses today has that default-pass shape. The one relationship graph OMNI already has (mission_graph) goes further: it fills missing links with a keyword match or the first available target, and it does this before its coverage checks run. An implementation that follows these existing patterns would therefore miss the mission's structural failures, even with the value-level KNOWN/UNKNOWN and provenance typing proposed in OMNI-FRONTIER-0002. The missed cases would be an unsupported rotating shaft, a belt drive with no tensioning, a leadscrew with no fixed/floating support, and a bearing with no axial retention. Prediction: v0.1 fails closed on structural omissions only if (a) component types and pattern roles declare required ports with cardinality, alternative ways to satisfy them, and provenance; (b) a closure step turns every required port in the assembly into an obligation before any compatibility rule runs; (c) the overall verdict is the worst verdict across that obligation set, and an empty or partially covered set can never be PASS; and (d) CAD obligations come only from bound interfaces, so an unbound port produces a finding and no geometry.

## Mechanism

KNOWN FACTS (from reading the repo):

(1) Default-pass aggregation is the standard pattern in the repo. workshop_part_validator.py:59-64, validation_engine.py:177-181 and knowledge_gate_validator.py:354-358 all start at "pass"/"passed" and only move down when a check adds a warning or blocker. rover_calculators.py:69 also starts at "PASS". With no applicable detector, the result is PASS.

(2) The existing relationship graph builds links from text similarity. mission_graph/enrichment.py:59-62 links a component to a data bus when bus.protocol is a substring of comp.interface. Lines 67-77 link ROS2 nodes to components when any word of 4 or more characters overlaps. The mission explicitly forbids treating semantic similarity as compatibility.

(3) The graph invents links to fill gaps. enrichment.py:99-116 sets any component or CAD feature that has no body_region_id to region_ids[0]. builder.py:482-484 runs enrich_graph before check_graph. reviewer.py:83-90 raises COMP_MISSING_BODY_REGION only when body_region_id is empty. So once any region exists, the missing-relationship warning can no longer fire: a missing relationship has been replaced by a made-up one.

(4) Coverage obligations are the same for every component regardless of type. reviewer.py:68-90 checks power rail, data bus and body region on every component, and missing links are only ever severity "warning". Nothing can say that a rotating shaft must have radial support (FAIL) while a passive plate needs no power rail.

(5) An empty graph gets a clean review. tests/test_mission_graph_phase6_review.py:204-205 asserts that review_graph on an empty graph returns issues == [].

(6) OMNI has one partial precedent for enumerating required items. golden_standard_validator.py:150-170 lists required artifacts, calculations and checks and counts the missing ones. But status "passed" only needs score >= 0.90, so up to 10% of required items can be missing and still pass. An empty requirement list gives 0.0 → "failed", which is fail-closed. reliability/gates.py:38-39 returns BLOCKED for an empty gate list. The rover calculation gate (reliability_service.py:659-664) turns missing required calculations into WARN, not UNKNOWN or BLOCKED.

(7) The CAD IR has no relationship concept. SubassemblySpec (cad_assembly_ir.py:248-270) holds flat lists of components, mounting features and fastener patterns. MechanicalComponentSpec (194-226) has no ports or interfaces. mechanical_component_library.py describes attachment only as a free-text mounting_hint.

WHY THIS MATTERS (inference): The mission's examples fall into two kinds. Value defects (bore ≠ seat diameter; speed rating unavailable) are handled by rules on existing edges combined with value-level UNKNOWN. Structural omissions ('rotating shaft has no support relationship', 'belt drive has no tensioning strategy') have no edge or value for a rule to evaluate. Value-level typing cannot flag a requirement that was never created. So a graph-plus-rules design with 0002's typing still reports nothing for omissions. Given the repo's default-pass patterns (1), the result becomes PASS or at most a warning. If an enrichment step like (3) runs first, a plausible link is invented and the omission disappears.

ARCHITECTURAL PROPOSAL (not a fact, not validated):
- ComponentType and PatternRole declare RequiredPort: {port_id, interface_type, role, cardinality, condition, satisfaction_alternatives, rule_provenance}.
  - condition example: applies only when motion=rotating.
  - satisfaction_alternatives example: 'two radial supports' OR 'one moment-capable support' OR 'host component provides internal support, with its load ratings as Facts that may be UNKNOWN'.
  - rule_provenance: STANDARD / HANDBOOK / OMNI_HEURISTIC etc.
- An InterfaceInstance binds exactly two ports, and every binding must be explicit (a user, Vega's proposal or pattern instantiation). Name or keyword similarity is never enough.
- An obligation closure pass creates one ObligationInstance per required port. Each gets PASS/WARN/FAIL/UNKNOWN plus rule_id, input fact_ids and provenance.
- An unbound required port is FAIL when its condition is known to hold, and UNKNOWN when the condition itself is unknown.
- A waiver is a separate record with provenance and a justification. It never deletes the obligation.
- Overall verdict: FAIL if any FAIL, else UNKNOWN if any UNKNOWN, else WARN if any WARN, else PASS. An empty obligation set gives UNKNOWN. PASS requires count(PASS or justified WARN) == count(obligations).
- Compatibility rules run per bound InterfaceInstance, using 0002-style Facts.
- InterfaceType owns per-side CAD feature templates (e.g., for shaft_to_bearing: a seat on the shaft side, a bore on the housing side, retention features conditional on role).
- CadObligations come only from bound instances whose compatibility verdict is not FAIL. Oli never gets geometry for an unbound or undecided port.
- Change to the mission's proposed flow: add an 'obligation closure' stage between 'interface graph' and 'compatibility analysis'.

EVIDENCE THAT COULD SUPPORT OR WEAKEN THIS (the Novelty Rule asks for this; not an experiment proposal):
- Supporting: take the mission's five patterns and remove one required relationship at a time. An edge-rule engine plus Fact typing emits no FAIL/UNKNOWN for those removals, while port closure flags each one.
- Weakening: Fact-typed required slots on records (e.g., shaft.radial_support_refs: Fact[list[ComponentId]] defaulting to UNKNOWN) catch every seeded omission, including context-dependent ones like fixed/floating, without a separate closure stage. In that case this hypothesis collapses into 0002.

Informal FrontierResearchScore (not authoritative): alignment 5, impact 5, information gain 4, generalizability 5 (ports and closure carry over to seals, springs, pneumatic fittings, electrical connectors, fixtures), novelty 3, experimentability 5 (seeded omissions on pure-Python fixtures, no CAD needed), risk 1, implementation cost 2.

## Competing hypotheses

- The decisive safeguard is an independently preserved assembly requirement contract, not closure over component ports. Component-derived closure can report PASS after an entire required subsystem disappears, because its obligations disappear with it. A requirement-driven evaluator can detect structural omissions without materializing a separate port-closure stage.
