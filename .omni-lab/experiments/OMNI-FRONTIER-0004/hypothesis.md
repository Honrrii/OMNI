# OMNI-FRONTIER-0004 — Hypothesis

OMNI-FRONTIER-0003 got as far as independent anchors, a versioned catalog, Kleene AND, best-of OR, and NOT_APPLICABLE for an empty domain once the inventory is declared complete. That still leaves one path by which the candidate can define away its own obligations: rule applicability. Every type-conditioned rule and every quantifier domain is evaluated over antecedent facts. Those facts are the instance's type membership, mode facts such as motion=rotating, selected-strategy tags, and completeness declarations. The candidate supplies all of them. If a false antecedent is accepted because a signal is missing or because the candidate asserted it, the result is NOT_APPLICABLE or exclusion from the domain. Four escape mutations then release a design with no FAIL or UNKNOWN. (E1) Reclassify a belt drive as an unregistered or generic type. (E2) Drop or flip the shaft motion fact. (E3) Author a candidate-side completeness declaration that makes a domain empty-and-complete. (E4) Satisfy an existential anchor with a witness chain that passes through a member no catalog rule covers. These correspond to required adversarial cases 7, 8 and 10. Refinement of 0003: a hash-bound candidate revision can be closed over its instances by construction, because the set of records it contains is the design of record. The open-world gap that actually matters is classification of those instances and their antecedent facts, not the inventory. Prediction: v0.1 fails closed only if applicability is judged with evidence, symmetrically with satisfaction. (i) NOT_APPLICABLE needs the same evidence as PASS: admissible provenance for the negated antecedent. (ii) Type membership is open-world. An instance whose type is not in the catalog, or is a generic type, makes every rule it could trigger UNKNOWN, adds a COVERAGE finding, and blocks any anchor witness that passes through it. (iii) An existential anchor passes only with a coverage-closed witness: every member has a catalog type and every rule those members trigger has a decided applicability. (iv) Each (rule, binding) cell is evaluated as a pair: applicability in {APPLIES, NOT_APPLICABLE, UNDETERMINED} and satisfaction in {T, F, U}. A frozen table maps each pair to PASS/WARN/FAIL/UNKNOWN before any aggregation. One consequence answers mission Q2: deleting a whole drive in a complete, hash-bound revision gives FAIL, not UNKNOWN. UNKNOWN applies only when the revision is declared a partial projection.

## Mechanism

KNOWN FACTS (read this turn):
F1. OMNI's existing conditional gates treat a missing trigger signal as "not applicable".
- backend/app/aeroforge/foundation.py:174-195 and 244-259 scan the mission text for keywords. With no keyword, the gate returns status 'not_applicable' with empty required_review_gates, blockers and blocked_outputs.
- Tests pin this behaviour for empty text: tests/test_aeroforge.py:161-163 and 525-527.
F2. The applicability decision can be supplied upstream. backend/app/export/export_manager.py:1011-1021 prefers a precomputed artifacts['aeroforge_intent']. If aerospace_detected is false or missing (.get default False), it returns not_applicable. An upstream artifact can therefore turn off a safety gate by asserting or omitting one field.
F3. backend/app/engineering/input_readiness_report.py:83-84: a check with no required inputs is READY. The empty antecedent set is treated as satisfied.
F4. An unknown type becomes concrete output. backend/app/cad/mechanical_component_library.py:276-284 looks types up by normalized name. Lines 336-349 return (50,30,15) and 'box' for any name not registered, instead of UNKNOWN.
F5. The 0003 precedent does not cover conditional rules. omni/testcube/arbiter.py:24-29 treats required_check_ids as unconditional: there is no applicability evaluation, so the arbiter never has to decide whether a check applies. backend/app/reliability/gates.py:6-11 and 37-41 have no applicability concept (empty list gives BLOCKED; otherwise max). backend/app/mission_graph/schemas.py:104 is the only UNKNOWN status literal found by grep.

WHY THIS IS THE REMAINING HOLE (inference):
- The two-source model makes RULES independent of the candidate, but not rule ANTECEDENTS.
- 0003's provenance-admissibility control (F7) applied to bindings only, not to type assignments, mode facts or completeness declarations.
- 0003 H3 made an empty domain NOT_APPLICABLE when the inventory is 'declared complete'. It never fixed who may author that declaration.
- Codex's seq-6 repair (a non-empty but incomplete universal domain gives UNKNOWN) still treats inventory as the open-world axis. For a candidate revision, the record set is known exactly, so the inventory can be closed structurally by hashing it. What is not known is whether record X 'is a belt_drive' or 'is rotating'.
- Each escape against 0003 semantics:
  - E1: a belt recorded as 'custom_flexible_part' is outside the domain of SYN-TENSION-001, so that root is NOT_APPLICABLE or PASS.
  - E2: motion omitted. 0003 made this UNKNOWN only for SYN-SUPPORT-001, and only because that one rule was written to read motion. There is no general rule.
  - E3: a candidate-authored complete declaration turns an empty domain into NOT_APPLICABLE.
  - E4: the anchor 'controlled rotary output' finds the witness motor→custom_part→output, so it PASSes. The shaft-support rule never fires on custom_part.

PROPOSED SEMANTICS (architectural proposal, not validated):
S1. Evidence tiers. Every antecedent fact carries source_class and author_role. NOT_APPLICABLE requires an admissible negative antecedent. The admissible set is frozen, e.g. a catalog type assignment backed by a MANUFACTURER/STANDARD part ID or a USER_PROVIDED engineering sign-off. Otherwise the result is UNDETERMINED.
S2. Types are open-world. The catalog declares for each type which triggers it can never satisfy, e.g. plate: never rotating_member. An unregistered or generic type can satisfy every trigger, so every rule whose trigger it cannot exclude gets UNDETERMINED applicability.
S3. Cell table:
- APPLIES×T=PASS, APPLIES×F=FAIL, APPLIES×U=UNKNOWN.
- NOT_APPLICABLE×any = NA. NA is counted in coverage and excluded from the verdict.
- UNDETERMINED×F=UNKNOWN. It is not FAIL, because the rule may not apply. This avoids false FAILs on valid designs with unclassified parts.
- UNDETERMINED×T=UNKNOWN. It is not PASS, because the rule is not shown to apply and passing an unproven check gives no coverage.
- UNDETERMINED×U=UNKNOWN.
S4. Aggregation. AND is FAIL>UNKNOWN>WARN>PASS. OR over alternatives takes the best result, but each installed alternative also keeps its own integrity cells (Codex seq-6 paired case). Existential anchor: PASS only with a coverage-closed witness. FAIL if no witness exists and the revision is complete. UNKNOWN otherwise. All-NA or empty is UNKNOWN.
S5. Completeness has two axes:
- (a) Instance closure is structural. The revision hash binds the record set, and the revision is 'design of record' unless it is marked PARTIAL_PROJECTION.
- (b) Classification closure holds iff every instance has an admissible catalog type. Candidate-authored completeness declarations are not admissible.
S6. CAD gating. Oli may receive geometry only for cells that are APPLIES×T with a coverage-closed context. Any UNDETERMINED cell touching a feature's participants produces a PendingCadObligation, never defaults. This closes F4's box fallback for this subsystem.

ADVERSARIAL CASE MAPPING (hand-derived, not executed):
1. Drive deleted, complete revision → FAIL. Partial projection → UNKNOWN.
2. Shaft without support → FAIL, if motion is admissibly known. Otherwise UNKNOWN.
3. Speed rating missing → APPLIES×U → UNKNOWN.
4. Bore mismatch → FAIL.
5. No tensioning strategy → FAIL.
6. Valid alternative → PASS via OR with integrity cells.
7. Unknown type → UNKNOWN plus a COVERAGE finding.
8. No catalog coverage for a required interface → the anchor witness is not coverage-closed → UNKNOWN.
9. Optional component absent → NA with admissible evidence → excluded, and the verdict is not lowered.
10. Deleting a component together with its rule → caught only if a surviving witness member triggers a rule that needs it, or the anchor witness breaks. If neither holds, this is a residual blind spot, identical to 0003's F10.

WHAT COULD WEAKEN THIS:
- 0003's semantics as frozen in seq 5-6 already block E1-E4 with no antecedent-evidence rule. That would mean the thread already closed this hole.
- A closed catalog enum that rejects unknown types at schema time blocks E1 and E4 at negligible cost. Note this would still leave generic types and wrong-but-valid catalog types open.
- Open-world typing floods realistic fixtures with UNKNOWN, e.g. brackets and plates, so that no valid control can reach PASS. That would be a degeneracy failure.

Informal FrontierResearchScore (not authoritative): alignment 5, impact 5, information gain 4, generalizability 5, novelty 4, experimentability 5, risk 1, implementation cost 2.

## Competing hypotheses

- The remaining problem is loss of dependency and scope information, not principally insufficient proof of rule applicability. S2–S5 can produce avoidable UNKNOWN results while still missing catalog omissions. A competing design evaluates requirement truth separately from coverage, preserves dependencies between alternative classifications, and requires explicit closure of each relevant inventory and relationship scope. A revision hash establishes identity, not engineering completeness.
