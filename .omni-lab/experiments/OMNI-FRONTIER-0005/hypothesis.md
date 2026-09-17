# OMNI-FRONTIER-0005 — Hypothesis

The Claude and Codex positions can be merged into one model. Only two of the five proposed dimensions are real, independent inputs to a verdict.

(1) Truth is computed by supervaluation over a finite set of admissible completions. Each unresolved classification, operating mode, strategy selection, existential witness or OPEN scope is one Dependency: a finite-domain choice point. truth=T only if the root is true in every admissible completion, F only if false in every one, U otherwise.

(2) Coverage is checked separately, against a versioned CoverageProfile. It cannot be derived from completions, because a rule that is absent from the catalog has no cell to evaluate.

Applicability is the same supervaluation applied to the antecedent. It is recorded, but it is not an independent verdict input. It matters for three things: NOT_APPLICABLE exclusion, coverage accounting, and CAD feature existence. Scope closure has two states per (revision, scope, category, abstraction boundary): CLOSED or OPEN. It acts on truth by adding completions that contain unrecorded members, and it is also a precondition for release. PARTIAL is a derived summary, not a primitive state.

This settles the disagreement as follows:
- **Codex was right about my 0004 cell table.** Its independent cell-by-cell aggregation is a sound but imprecise Kleene approximation, and it loses correlations (Codex counterexamples c1 and c2).
- **Codex was right about hashes.** I withdraw 0004 S5a: a revision hash does not close any scope.
- **My point that NOT_APPLICABLE needs evidence still holds, in a narrower form.** A fact may narrow the completion domain, including removing the 'antecedent true' completions, only if its provenance is admissible for that kind of fact.

**Prediction:** a frozen evaluator with these semantics reproduces all 12 required verdict cases and all 7 adversarial examples with 0 unsafe PASS. On c2 it gives FAIL where the per-cell table gives UNKNOWN. For one unresolved A|B classification it emits one Finding, where the per-cell table emits N.

## Mechanism

A. SHARED SEMANTIC CORE (a proposal, not yet validated)

A1. Choice points (Dependency)
- Each Dependency has kind ∈ {CLASSIFICATION, OPERATING_MODE, STRATEGY, WITNESS_BINDING, SCOPE_EXTENSION} and a domain.
- The domain is a finite set of admissible values, or UNBOUNDED.
- Exclusivity is built into the structure: "exactly one of T1/T2" is one variable with domain {T1,T2}, not two booleans. v0.1 allows no constraints between variables.
- UNBOUNDED covers an unmapped catalog type. It cannot be enumerated, so any root whose truth depends on it is U.
- If a root depends on more than K choice points (e.g. K=6, 64 completions), it is U with Finding EVALUATION_BOUND.

A2. Admissibility narrows domains
- A fact removes values from a domain only if its Provenance (source_class, author_role) is in the frozen admissible set for that fact kind.
- The same set applies to positive and negative use.
- v0.1 policy table:
  - DESIGN_CHOICE (which strategy or components are installed): candidate-authored is admissible, because the design is the candidate's to declare.
  - CLASSIFICATION: requires a catalog part ID or a human engineering sign-off.
  - OPERATING_MODE: requires derivation from a contract anchor or catalog role, or sign-off.
  - SCOPE_CLOSURE: never authored by the candidate generator. It is held with the contract or revision record under a named authority.
- This keeps my 0004 S1 but moves it onto domain narrowing. An inadmissible assertion leaves the domain wide and also emits INADMISSIBLE_EVIDENCE.

A3. Truth
- Evaluate the root expression (AND, OR, NOT, implication, bounded count over a declared domain) in every completion.
- T if true in all, F if false in all, U otherwise.
- Over an OPEN scope, completions include 'one more unrecorded member of this category'. Consequences:
  - A universal root whose observed members all pass is U.
  - An observed counterexample gives F.
  - An existential root with an admissible, completion-invariant witness gives T.
  - A missing witness is F if the scope is CLOSED, U if OPEN.
- This is exactly Codex 0003 seq-6's quantifier table, now derived rather than stipulated.

A4. Applicability
- Supervaluate the antecedent.
- NOT_APPLICABLE is allowed only if (i) the antecedent is false in every admissible completion, every domain-narrowing fact is admissible (A2), and (ii) for an empty quantified domain, the governing ScopeDeclaration is CLOSED.
- APPLIES means the antecedent is true in every completion. Anything else is UNDETERMINED.
- UNDETERMINED does not force truth=U. For A⇒R with R true in all completions, truth=T (Codex c1). A feature whose existence depends on A still cannot become CAD (see D).

A5. Coverage
- CoverageProfile@version maps each type, interface type or pattern to the validation categories it requires.
- COVERED: every required category has a rule that was executed and produced an Evaluation.
- UNCOVERED: the profile names a category with no executed rule (the 'uncovered interface' case). Removing a rule does not remove the category.
- UNKNOWN: the subject has no profile entry (an unmapped type, or a profile without this interface type).
- Coverage never feeds the completion set.

A6. Scope
- ScopeDeclaration applies per (revision_hash, scope_path, category, abstraction_boundary), with category ∈ {COMPONENT, INTERFACE, RELATIONSHIP:<kind>, REQUIREMENT, RULE_COVERAGE}.
- State is CLOSED only with an admissible authority. With no declaration, the state is OPEN.
- Closure is independent per category and per scope. A CLOSED support inventory for A says nothing about B.
- A declaration inside a subassembly governs only catalog rules inside that subassembly. Contract anchors use declarations held at revision level with the contract (0003 H2).
- REQUIREMENT and RULE_COVERAGE closure are closure relative to a version, not absolute completeness: 'this contract@v and profile@v are accepted as the sets of record'.
- A purchased actuator gives COMPONENT CLOSED at its abstraction boundary with RELATIONSHIP:internal_support OPEN, unless an admitted abstraction contract supplies the evidence (Codex 0004).
- Each Revision carries status ∈ {DESIGN_OF_RECORD, INTERMEDIATE}.

A7. Dependency-preserving Findings
- For each U root, compute its essential dependencies: choice point v is essential if two admissible completions that differ only in v give different truth.
- Finding identity = hash(kind, sorted essential dep IDs). It carries affected_eval_ids.
- One unresolved A|B classification that changes K rules therefore yields one UNRESOLVED_DEPENDENCY finding listing K evaluations, not K separate UNKNOWNs.

B. DETERMINISTIC VERDICT MAPPING

B1. Per root
- truth=F → FAIL. F already accounts for OPEN completions, so it is safe under any coverage.
- truth=U → UNKNOWN.
- truth=T and coverage≠COVERED → UNKNOWN (COVERAGE_GAP or UNMAPPED_TYPE).
- truth=T, COVERED, applicability=NOT_APPLICABLE → NA. NA counts toward coverage and is excluded from the verdict.
- truth=T, COVERED → PASS, or WARN if the rule is ADVISORY or a valid waiver disposition applies.

B2. Aggregate release verdict
- FAIL if any MANDATORY root is FAIL. A proven violation outranks gaps.
- Otherwise UNKNOWN if any of these holds: a mandatory root is UNKNOWN; any referenced release scope (revision COMPONENT, INTERFACE, RELATIONSHIP inventories, REQUIREMENT@contract, RULE_COVERAGE@profile) is OPEN; the revision is INTERMEDIATE; the mandatory contract is empty; every root is NA.
- Otherwise WARN if any WARN.
- Otherwise PASS.

B3. The 12 required cases
1. T+COVERED+CLOSED → PASS.
2. T+UNCOVERED → UNKNOWN. WARN cannot waive missing validation knowledge.
3. T+OPEN scope → the root may be PASS only if T holds in every completion (e.g. an existential witness). The aggregate is UNKNOWN with SCOPE_OPEN.
4. UNKNOWN truth → UNKNOWN.
5. FALSE → FAIL.
6. NA with an admissible, completion-invariant negated antecedent → NA: excluded, counted.
7. NA without sufficient evidence → UNDETERMINED:
   - consequent true in all completions and COVERED → PASS for that root, with no CAD for features conditional on the antecedent;
   - consequent false in all completions → U → UNKNOWN (the antecedent-false completion makes it vacuously true);
   - otherwise UNKNOWN.
8. OR with one branch T in all completions → T → PASS. Installed components of the unselected branch keep their own catalog integrity roots (Codex 0003 seq-6 paired case).
9. All branches F → FAIL.
10. Branches {F,U} → UNKNOWN; {T,U} → PASS. Correlated branches (A∨¬A over one dependency) are T under supervaluation, where Kleene gives U.
11. Empty domain + CLOSED → NA (vacuous T, coverage record emitted). It does not satisfy any independent existential anchor.
12. Empty domain + OPEN → U → UNKNOWN.

C. ADVERSARIAL EXAMPLES (derived by hand)
- Unknown type:
  - The type domain is UNBOUNDED, so every root whose truth depends on that instance is U, including a witness chain through it (this closes 0004 E1/E4 without a special 'coverage-closed witness' rule).
  - Coverage is UNKNOWN.
  - Result: one UNMAPPED_TYPE finding plus one UNRESOLVED_DEPENDENCY finding → UNKNOWN.
  - Roots that do not depend on the instance's type still evaluate normally.
- Missing relationship:
  - Shaft with admissible motion=rotating: support scope OPEN → U; CLOSED with no admissible support binding → F.
  - Motion undetermined: completions {rotating→F, static→NA/T} → U, with the finding keyed on motion(shaft), not on 'support missing'.
  - An inadmissible gap-filler binding is treated as absent and also emits INADMISSIBLE_EVIDENCE.
- Whole subsystem deletion:
  - Contract anchor ∃ realization(controlled_rotary_output) has no witness.
  - Revision-level realization scope CLOSED → FAIL. OPEN, or the only declaration was deleted with the subsystem → UNKNOWN.
  - The hash alone never selects the label.
- Uncovered interface:
  - The profile requires a category with no rule → UNCOVERED → UNKNOWN even when every executed rule is T.
- Classification dependency A|B:
  - Enumerate both completions. Both violate → FAIL (Codex c2). Both satisfy → PASS for truth, while applicability-dependent CAD stays PENDING. They differ → UNKNOWN.
  - One Finding keyed on classification(p).
- Valid alternative: see case 8.
- Partial design:
  - INTERMEDIATE caps the aggregate at UNKNOWN and forces CAD to PENDING.
  - Proven FAILs (observed universal counterexamples) remain FAIL.
  - Missing existential witnesses under OPEN scope are UNKNOWN, not FAIL.

D. CAD GATING RULE

A CADObligation is EXECUTABLE for feature f only if ALL of the following hold:
1. The rule that generates f has applicability=APPLIES. Being true in all completions is not enough; f's existence must be completion-invariant.
2. Every prerequisite Evaluation is PASS, or WARN from an advisory rule. A waiver never satisfies a prerequisite that carries geometry.
3. Every participant is admissibly bound and has a mapped catalog type.
4. Coverage is COVERED for f's rule and for every participant interface type.
5. Every ScopeDeclaration in f's dependency cone is CLOSED.
6. Every geometry parameter is a known Fact with admissible provenance. Defaults and fallbacks are forbidden, which directly contradicts the unregistered-name → (50,30,15)/'box' fallback in mechanical_component_library.py:336-349.
7. The revision is DESIGN_OF_RECORD.

Otherwise f is PENDING, with blocking_refs naming the exact dependency IDs, finding IDs or scope IDs.

E. MINIMAL v0.1 STRUCTURES (not implemented)
- Provenance{prov_id, source_class, author_role, source_locator, source_version, derived_by_rule@ver, input_fact_ids, revision_hash}
- Fact{fact_id, subject_ref, kind, value|UNKNOWN, prov_id}
- Requirement{req_id@ver, origin: CONTRACT|CATALOG_RULE, expr, severity: MANDATORY|ADVISORY, prov_id}
- Rule{rule_id@ver, subject_selector, antecedent_expr, consequent_expr, coverage_categories, cad_feature_templates, waivable, prov_id}
- CoverageProfile{profile_id@ver, subject_type→required_categories}. This is part of the catalog, not a new topic.
- Revision{revision_hash, status}
- ScopeDeclaration{scope_id, revision_hash, scope_path, category, abstraction_boundary, state: CLOSED|OPEN, authority_role, prov_id}
- Dependency{dep_id, kind, subject_ref, domain: values|UNBOUNDED, narrowing_fact_ids}
- RuleBinding{binding_id, rule_id@ver, participant_refs, prov_id, admissible}
- Evaluation{eval_id, root_ref, contract@v, catalog@v, profile@v, revision_hash, applicability, truth, coverage, dependency_cone, essential_deps, completions_evaluated, witness_refs, counterexample_refs, input_fact_ids}
- Finding{finding_id=hash(kind, essential_deps|rule|scope), kind ∈ {VIOLATION, UNRESOLVED_DEPENDENCY, COVERAGE_GAP, UNMAPPED_TYPE, SCOPE_OPEN, INADMISSIBLE_EVIDENCE, EVALUATION_BOUND}, affected_eval_ids, verdict}
- CADObligation{obligation_id, feature_template@ver, participants, generating_eval_ids, state: EXECUTABLE|PENDING, blocking_refs, parameter_fact_ids}

F. WHAT WOULD REFUTE OR WEAKEN THIS
- An unsafe PASS: a case where a root is T in all admissible completions but the design is defective within the frozen synthetic oracle. This would show the admissibility policy in A2 is too permissive.
- A case where coverage must enter the completion set (would weaken the claim that coverage is irreducible).
- A case where a single category needs a primitive PARTIAL state with distinct evaluable semantics.
- The per-variable essential-dependency key merges two truly independent uncertainties, or splits one.
- The release-scope precondition in B2 is shown redundant, or shown to false-UNKNOWN every realistic valid control (degeneracy).

## Competing hypotheses

- The remaining error is premature aggregation: separate root verdicts and a scalar coverage result can still discard dependencies that supervaluation preserved internally. v0.1 needs joint evaluation of mandatory obligations and coverage attached to their proof dependencies. This is a small refinement of the shared model, but it contradicts the claim that A1–B3 already reproduce every required case: B2 loses the correlated FAIL, and B3’s empty-domain rule conflates universal and existential requirements.
