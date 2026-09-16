# OMNI Component Intelligence v0.1
## Frozen TestCube Implementation Specification

Status: IMPLEMENTATION HYPOTHESIS — NOT ENGINEERING VALIDATED

Research basis:

- OMNI-FRONTIER-0003
- OMNI-FRONTIER-0004
- OMNI-FRONTIER-0005

Agreement between AI providers does not constitute engineering validation.

This document freezes one architecture for controlled implementation and
deterministic testing. TestCube candidates must implement this contract rather
than redesign it.

The purpose of the trial is to determine whether two isolated implementations
can satisfy the same engineering semantics from the same repository baseline.


# 1. Objective

Implement Component Intelligence v0.1 as a deterministic, inspectable,
provenance-aware mechanical assembly reasoning subsystem for OMNI.

The subsystem must allow OMNI to represent components, interfaces,
requirements, engineering facts, relationships, rule coverage, uncertainty,
and CAD obligations without silently converting missing engineering knowledge
into plausible geometry or PASS results.

Component Intelligence v0.1 is not a component catalog alone.

It must answer:

- what components are present
- what engineering requirements apply
- how components are connected
- what relationships are required
- whether represented interfaces are compatible
- what required relationships are missing
- what information is unknown
- whether validation knowledge exists for a requirement
- whether the relevant engineering scope is complete
- what CAD features are justified
- why each result was produced
- where supporting engineering facts came from


# 2. Non-Goals

v0.1 must NOT attempt to provide:

- a comprehensive commercial component database
- automatic web scraping
- machine learning
- autonomous knowledge mutation
- manufacturer specification invention
- tolerance invention
- semantic-similarity-based compatibility
- a complete CAD engine
- a rewrite of Oli
- a rewrite of OMNI orchestration
- automatic acceptance of LLM-generated engineering facts
- automatic optimization of entire machines

The implementation should establish a trustworthy architecture that later
versions can expand.


# 3. Initial Component Families

v0.1 must support representation of at least these families:

1. fasteners / joining components
2. shafts / rotary members
3. bearings / bushings
4. couplings
5. gears / pulleys / sprockets / belts / chains
6. motors / rotary actuators
7. linear-motion components
8. structural members

The seed knowledge base should remain intentionally small.

Target approximately 20–40 generic representative component records rather
than thousands of catalog entries.

Manufacturer-specific performance values must not be invented.


# 4. Required Architectural Concepts

The implementation must provide concepts equivalent to the following.

Exact class names may differ, but the semantics may not.

## 4.1 EngineeringFact

An engineering value must not be represented only by a raw scalar.

A fact must be able to preserve:

- value
- units where applicable
- epistemic state
- provenance
- optional source reference
- optional notes or assumptions

Required epistemic states:

- KNOWN
- UNKNOWN
- ASSUMED

UNKNOWN must remain distinct from zero, null-as-default, omitted, and PASS.

ASSUMED must remain distinguishable from KNOWN.


## 4.2 Provenance

Engineering knowledge must support source classes equivalent to:

- STANDARD
- MANUFACTURER
- HANDBOOK
- OMNI_VALIDATED
- OMNI_HEURISTIC
- USER_PROVIDED

LLM agreement is not engineering provenance.

An LLM-produced value must not automatically become STANDARD,
MANUFACTURER, HANDBOOK, or OMNI_VALIDATED.

Provenance must be attachable to at least:

- engineering facts
- component properties
- requirements
- rules
- interfaces
- relationships
- derived obligations
- findings
- CAD obligations


## 4.3 Component

A component must have:

- stable identifier
- family
- subtype
- structured engineering facts
- declared interfaces or ports
- provenance
- optional standard or source metadata

Component identity and component engineering type must remain explicit.

Unknown or unmapped component types must not silently become a generic
compatible component.


## 4.4 Interface

Interfaces must be typed engineering entities.

Examples include:

- shaft_to_bearing
- shaft_to_coupling
- shaft_to_gear
- bearing_to_housing
- threaded_joint
- motor_to_mount
- motor_to_coupling
- linear_rail_to_structure
- pulley_to_belt
- sprocket_to_chain

An interface representation must be capable of carrying:

- participants
- mating geometry
- relevant dimensions
- alignment requirements
- retention requirements
- load-transfer semantics
- compatibility state
- provenance
- CAD obligations or derived CAD requirements


## 4.5 Requirement

Requirements must be independent of the candidate design that is being
evaluated.

A candidate must not be able to obtain PASS by deleting the components or
relationships that would otherwise create the requirement.

Requirements must distinguish at least:

- mandatory
- advisory

Mandatory requirements participate in release verdicts.

Advisory requirements may produce WARN without causing a mandatory FAIL.


## 4.6 Rule

Rules must be versioned, deterministic engineering knowledge.

A rule must support concepts equivalent to:

- rule identifier
- applicability predicate
- satisfaction predicate
- provenance
- version
- required inputs
- relevant engineering domain

Rules may be conditioned on selected design choices.

Examples:

If a bearing is selected:
- support/interface rules may apply
- retention rules may apply
- relevant dimensional compatibility rules may apply

If a belt drive is selected:
- alignment and tensioning rules may apply

If a leadscrew stage is selected:
- support, nut, carriage, and alignment rules may apply


## 4.7 Dependency

Unresolved engineering choices that affect multiple rules must remain
correlated.

The evaluator must support dependencies equivalent to:

- finite-domain choice
- joint/correlated finite-domain choice
- UNBOUNDED or otherwise unresolved domain

Example:

A component may be classification A or B.

If that single unresolved classification changes four rules, the evaluator
must not treat those four uncertainties as independent choices and construct
combinations that cannot exist physically.


## 4.8 ScopeDeclaration

Engineering completeness must be explicit.

A Git commit, revision identifier, content hash, or candidate identity proves
which design revision is being evaluated.

It does NOT prove engineering completeness.

Required primitive scope states:

- CLOSED
- OPEN

PARTIAL may exist only as a derived presentation state.

The system must be capable of expressing closure independently for domains
such as:

- component inventory
- interface inventory
- relationship inventory
- requirement inventory
- relevant rule/coverage domain

A required OPEN scope prevents release as PASS.


## 4.9 Evaluation

Evaluation must keep important dimensions inspectable rather than collapsing
everything immediately into one score.

Required concepts include:

Applicability:
- APPLIES
- NOT_APPLICABLE
- UNDETERMINED

Engineering truth:
- TRUE
- FALSE
- UNKNOWN

Coverage:
- COVERED
- UNCOVERED
- UNKNOWN

Scope:
- CLOSED
- OPEN

Final external verdict:
- PASS
- WARN
- FAIL
- UNKNOWN


# 5. Applicability Semantics

NOT_APPLICABLE is not a default.

It must be justified by admissible evidence that the rule antecedent is false.

Missing information must not automatically produce NOT_APPLICABLE.

For example:

motion type missing

must not silently mean:

shaft rotation rule does not apply.

Instead, applicability is UNDETERMINED unless the negated antecedent is
supported by adequate evidence.


# 6. Truth and Dependency Semantics

v0.1 must preserve dependencies while evaluating requirements.

The implementation may use explicit completion enumeration for the bounded
v0.1 problem size or another deterministic method with equivalent semantics.

For a finite unresolved dependency domain:

- TRUE means the requirement evaluates true for every admissible completion.
- FALSE means the requirement evaluates false for every admissible completion
  or is otherwise deterministically disproven according to the requirement
  semantics.
- UNKNOWN means admissible completions disagree or required information is
  unresolved.

The implementation must not erase correlations merely to simplify evaluation.


# 7. Coverage Semantics

Coverage is distinct from engineering truth.

Examples:

The design may actually be mechanically valid, but OMNI may lack a rule capable
of verifying an interface.

That situation is not PASS.

Required validation knowledge absent for a mandatory obligation must produce
an inspectable coverage finding and prevent PASS.

No rule found is NOT equivalent to no defect found.


# 8. Scope Semantics

Scope closure must be explicitly declared or deterministically established.

CLOSED means the evaluator may treat the relevant domain as complete within the
declared abstraction boundary.

OPEN means additional members or relationships may exist.

Required OPEN scopes prevent PASS.

A revision hash alone must never convert OPEN to CLOSED.


# 9. Logical Composition

v0.1 must support deterministic semantics for at least:

- A AND B
- A OR B
- at least one of A/B/C
- conditional requirements
- universal requirements over a declared domain
- existential requirements over a declared domain
- required cardinality
- bounded cardinality
- optional relationships
- mutually exclusive strategy alternatives

The implementation may choose an expression tree, structured predicates, or
another deterministic representation.

The chosen representation must preserve dependency information.


# 10. Empty-Domain Semantics

Logical truth and engineering requirement satisfaction must remain distinct.

Example:

"all bearings satisfy requirement X"

with zero bearings and a CLOSED bearing domain may be logically true as a
universal expression.

That does NOT satisfy a separate requirement that at least one bearing/support
must exist.

Required semantics:

Closed empty universal domain:
- universal expression may evaluate TRUE

Closed empty existential domain:
- existential expression evaluates FALSE

Open relevant domain:
- result is UNKNOWN when completeness could affect the answer

Vacuous logical truth must never allow deletion of a required subsystem to
produce an engineering PASS.


# 11. Mandatory Verdict Semantics

Final verdict derivation must be deterministic.

At minimum:

Mandatory engineering requirement proven FALSE:
    FAIL

Mandatory engineering result unresolved:
    UNKNOWN

Mandatory validation knowledge UNCOVERED:
    UNKNOWN

Required scope OPEN:
    UNKNOWN

Candidate explicitly marked INTERMEDIATE:
    UNKNOWN

Mandatory contract empty or entirely excluded:
    UNKNOWN

Mandatory requirements proven TRUE,
required coverage established,
required scopes CLOSED,
candidate final,
and no mandatory release blocker:
    eligible for PASS or WARN

If mandatory release conditions are satisfied but an advisory condition is not
fully TRUE:
    WARN

If mandatory and advisory release conditions are satisfied:
    PASS

v0.1 has no waiver mechanism.

An implementation must never derive PASS merely because no FAIL finding exists.


# 12. Assembly Patterns

v0.1 must support reusable assembly-pattern knowledge.

Required initial patterns:

## Supported Shaft

shaft
 -> bearing/support
 -> structure/housing
 -> retention where required

## Motor to Shaft

motor
 -> coupling
 -> shaft
 -> support
 -> driven load

## Motor to Leadscrew Stage

motor
 -> coupling
 -> leadscrew
 -> support
 -> nut
 -> carriage
 -> linear guide

## Belt Drive

motor
 -> pulley
 -> belt
 -> driven pulley
 -> shaft
 -> support
 -> tensioning strategy

## Geared Output

motor
 -> gear/reduction stage
 -> output shaft
 -> support
 -> driven load

Patterns must not automatically create PASS.

They provide requirements, roles, relationships, or validation structure.


# 13. Required Mechanical Reasoning

The implementation must be capable of expressing deterministic checks
including:

- bearing bore versus shaft seat compatibility
- coupling bore versus shaft dimensions
- required shaft support
- required retention where defined by the applicable rule/pattern
- motor/coupling/shaft relationship consistency
- belt-drive tensioning requirement
- leadscrew support requirements
- missing required relationships
- missing required facts
- missing validation-rule coverage
- unknown component type

No manufacturer rating may be fabricated to satisfy a check.


# 14. Findings

Every significant evaluator result must be explainable.

A Finding must contain concepts equivalent to:

- stable finding/rule/requirement identifier
- affected components/interfaces
- verdict or finding state
- observed evidence
- expected condition
- explanation
- provenance
- dependencies where relevant

UNKNOWN must explain why it is unknown.

Examples:

- missing engineering property
- unresolved classification
- open relationship scope
- uncovered rule
- unsupported component type


# 15. CAD Obligation Contract

Component Intelligence does not replace Oli.

It supplies engineering obligations to CAD.

A CADObligation must be traceable to validated engineering knowledge.

Examples:

Bearing interface may create:

shaft:
- bearing seat
- shoulder or equivalent locating feature
- retention feature where required

housing:
- bearing bore or pocket
- outer-race locating/retention feature where required
- assembly access where required

A CAD obligation must preserve:

- target component/interface
- required feature
- known dimensions
- unresolved inputs
- provenance
- release state


# 16. CAD Release Safety

Oli must not receive unresolved engineering information as if it were concrete
validated geometry.

A concrete CAD obligation must not be released when a mandatory prerequisite
depends on:

- UNKNOWN engineering truth
- UNDETERMINED applicability
- UNCOVERED mandatory validation knowledge
- OPEN required scope
- unresolved required dependency

The implementation may emit a blocked/unresolved CAD obligation for inspection.

It must not silently substitute arbitrary geometry.


# 17. Required Adversarial Fixtures

TestCube evaluation must include deterministic cases equivalent to all of the
following.

## Fixture 1 — Entire Required Drive Missing

Mission requires controlled rotary output.

Candidate contains no motor, transmission, or output subsystem.

Expected:
- not PASS
- mandatory requirement unsatisfied or unresolved according to frozen input
  completeness
- deletion of the subsystem must not delete the requirement


## Fixture 2 — Unsupported Rotating Shaft

Rotating shaft exists.

Required support relationship is absent in a CLOSED relationship scope.

Expected:
- FAIL


## Fixture 3 — Unknown Bearing Rating

Required operating speed is known.

Bearing speed capability is UNKNOWN.

Expected:
- UNKNOWN

Forbidden:
- PASS
- fabricated rating


## Fixture 4 — Bore Mismatch

Shaft seat diameter and bearing bore are both known and incompatible.

Expected:
- FAIL


## Fixture 5 — Belt Without Tensioning

Belt-drive pattern applies.

Required tensioning strategy is absent in a CLOSED relevant scope.

Expected:
- FAIL


## Fixture 6 — Valid Alternative Strategy

Requirement permits strategy A OR strategy B.

B is fully proven valid.

Expected:
- requirement may PASS even if A fails or is absent, according to the explicit
  alternative semantics


## Fixture 7 — Unknown Component Type

Component exists but cannot be mapped to the registered engineering type
catalog.

Expected:
- UNKNOWN
- coverage/type finding

Forbidden:
- generic compatibility PASS


## Fixture 8 — Missing Rule Coverage

Required interface exists.

No registered validation knowledge covers the mandatory interface requirement.

Expected:
- UNKNOWN
- UNCOVERED finding

Forbidden:
- PASS


## Fixture 9 — Optional Component Absent

Explicitly optional component is absent.

Expected:
- no failure solely because of its absence


## Fixture 10 — Self-Erasing Rule

Candidate removes a component and thereby removes the instance-level rule that
would have checked that component.

A candidate-independent requirement still requires the corresponding
engineering function.

Expected:
- not PASS


## Fixture 11 — Correlated Classification

One component may be type A or type B.

The unresolved classification affects multiple requirements.

Expected:
- preserve one correlated dependency
- do not invent impossible independent combinations


## Fixture 12 — Open Relationship Scope

Required relationship inventory is OPEN.

No current defect is observed.

Expected:
- UNKNOWN

Forbidden:
- PASS


## Fixture 13 — Closed Empty Existential Domain

Requirement states that at least one valid support must exist.

Support domain is CLOSED and empty.

Expected:
- FAIL


## Fixture 14 — Closed Empty Universal Domain

Universal statement over a CLOSED empty domain may be logically true.

If a separate existence requirement applies, that requirement still fails.

Expected:
- no vacuous engineering PASS


## Fixture 15 — Unresolved CAD Input

Mechanical relationship or required dimension remains UNKNOWN.

Expected:
- no released concrete CAD geometry obligation using an invented value


## Fixture 16 — Fully Valid Final Assembly

All mandatory requirements TRUE.
Required rules COVERED.
Required scopes CLOSED.
Candidate FINAL.
No mandatory blocker.
Advisory requirements satisfied.

Expected:
- PASS


## Fixture 17 — Crossed Coverage / Dependency Case

Alternative classifications or strategies are correlated with the validation
rules that execute.

Coverage from one completion must not be incorrectly combined with truth from a
different incompatible completion.

Expected:
- never unsafe PASS


# 18. Determinism

Given identical:

- component data
- requirements
- rule catalog
- provenance
- dependency domains
- scope declarations
- candidate assembly

the evaluator must produce identical results.

The correctness-critical path must not depend on stochastic LLM judgment.


# 19. Fail-Closed Requirements

The following behaviors are forbidden:

- missing value converted to a numeric default for validation
- missing property treated as PASS
- missing rule treated as PASS
- unknown component type treated as compatible
- empty detector output treated as PASS
- revision hash treated as engineering completeness
- LLM agreement treated as trusted provenance
- semantic similarity treated as mechanical compatibility
- unresolved dependency discarded
- OPEN required scope treated as CLOSED
- provider/model confidence substituted for engineering evidence
- unresolved mandatory engineering information emitted as validated CAD
  geometry


# 20. Seed Knowledge

Seed data should use generic components unless real specification data with
proper provenance already exists in the repository.

Do not fabricate commercial specifications.

Seed knowledge should be sufficient to exercise:

- shaft/bearing relationships
- motor/coupling/shaft relationships
- belt drive
- leadscrew stage
- structural support relationships


# 21. Proposed Integration Boundary

A successful v0.1 should support a flow conceptually equivalent to:

mission requirements
 -> structured engineering requirements
 -> candidate component architecture
 -> component/interface graph
 -> dependency and scope model
 -> deterministic evaluation
 -> findings
 -> CAD obligations
 -> Oli CAD generation
 -> QaZ validation

Oli must not invent missing mechanical relationships to make geometry work.


# 22. Suggested Module Boundary

The implementation should remain isolated from unrelated OMNI systems.

A reasonable location is:

    omni/component_intelligence/

Candidates may choose an internal file breakdown that fits the existing
repository style.

The subsystem should expose a small public API for:

- registering/loading component knowledge
- building or validating an assembly representation
- evaluating requirements
- returning findings
- returning CAD obligations

Do not perform unrelated refactors.


# 23. Test Requirements

Candidates must add deterministic automated tests.

Tests must cover:

- schema validation
- provenance validation
- deterministic IDs or ordering where relevant
- component/interface validation
- requirement evaluation
- dependency preservation
- scope closure
- rule coverage
- applicability semantics
- PASS/WARN/FAIL/UNKNOWN mapping
- assembly patterns
- CAD gating
- every required adversarial fixture in this specification

UNKNOWN must be explicitly asserted in tests where required.

Tests that merely assert "does not crash" are insufficient.


# 24. Required Deliverables

Each TestCube candidate must produce:

- Component Intelligence implementation
- structured schemas/models
- component/interface representation
- requirement representation
- provenance representation
- dependency representation
- scope representation
- rule representation
- deterministic evaluator
- finding representation
- assembly-pattern support
- CAD obligation contract
- small seed knowledge set
- deterministic tests
- concise developer documentation

Do not commit, push, merge, or deploy during candidate generation.


# 25. Acceptance Criteria

A candidate is eligible for consideration only if:

- required tests pass
- existing relevant repository tests remain passing
- required adversarial fixtures are implemented
- no required UNKNOWN case silently becomes PASS
- no fabricated engineering values are introduced
- correlations are preserved where required
- missing rule coverage blocks PASS
- required OPEN scope blocks PASS
- CAD gating prevents unresolved mandatory information from becoming validated
  concrete geometry
- provenance is preserved
- outputs are deterministic
- implementation remains reasonably modular and inspectable

Passing tests does not establish real-world engineering validity.

It establishes conformance to this frozen implementation hypothesis.


# 26. Research Status

The architecture in this specification is based on controlled multi-model
research and adversarial critique.

Frontier research did not establish that the architecture is physically or
formally complete for all mechanical systems.

Component Intelligence v0.1 is therefore an experimental engineering reasoning
foundation.

Future validation may revise this architecture.

Any such revision must occur through a new version/specification rather than
silently changing the meaning of this frozen TestCube trial.
