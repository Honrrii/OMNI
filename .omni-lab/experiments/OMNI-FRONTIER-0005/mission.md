# OMNI Frontier Continuation Mission
## Component Intelligence v0.1 — Scope, Coverage, and Dependency Semantics

This research continues:

- OMNI-FRONTIER-0003
- OMNI-FRONTIER-0004

Inspect the archived messages from those threads before answering.

Do not restart the broad Component Intelligence architecture discussion.
Do not perform a broad repository survey.

The only purpose of this shift is to resolve the remaining formal disagreement
between the last Claude and Codex positions.

## Established Direction

The prior research has already established strong support for:

- candidate-independent engineering requirements
- versioned type/rule knowledge
- candidate assembly graphs
- explicit UNKNOWN semantics
- provenance-aware facts
- design-induced obligations
- fail-closed CAD generation
- prevention of vacuous PASS

Do not debate those points again unless they conflict with the formal model
proposed here.


## Remaining Disagreement

Claude proposed that rule applicability itself must be evidence-bearing:

    applicability ∈ {
        APPLIES,
        NOT_APPLICABLE,
        UNDETERMINED
    }

and argued that UNKNOWN/generic types, uncovered rules, or unsupported witness
chains must prevent PASS.

Codex countered that the deeper issue is loss of dependency and scope
information. It proposed separating:

- requirement truth
- validation/rule coverage
- dependency structure
- inventory/relationship scope closure

Codex also argued:

    revision identity != engineering completeness

Resolve these positions.


## Required Research Result

Determine whether Component Intelligence v0.1 should represent the following
as independent dimensions.

### Applicability

Possible states:

- APPLIES
- NOT_APPLICABLE
- UNDETERMINED

Determine what evidence is required before NOT_APPLICABLE is allowed.


### Satisfaction / Truth

Possible states:

- TRUE
- FALSE
- UNKNOWN

This represents whether the engineering condition itself is satisfied.


### Coverage

Possible states:

- COVERED
- UNCOVERED
- UNKNOWN

Coverage asks whether OMNI possesses and executed the required validation
knowledge.

A condition must not PASS merely because no applicable rule was found.


### Scope Completeness

Investigate explicit closure states for inventories and relationship domains,
for example:

- CLOSED
- OPEN
- PARTIAL

Resolve whether closure applies independently to:

- component inventory
- interface inventory
- relationship inventory
- requirement inventory
- rule coverage domain

A candidate revision hash identifies a design revision but must not, by itself,
imply that these scopes are complete.


### Dependencies

The representation must preserve dependencies between:

- alternate classifications
- alternate design strategies
- existential witnesses
- rule applicability
- requirement satisfaction
- coverage findings

Avoid multiplying independent UNKNOWN findings when several uncertainties are
actually consequences of one unresolved classification or dependency.


## Final Verdict

Define a deterministic mapping from the internal dimensions to:

- PASS
- WARN
- FAIL
- UNKNOWN

At minimum, determine semantics for:

1. TRUE + COVERED + CLOSED scope
2. TRUE + UNCOVERED
3. TRUE + OPEN scope
4. UNKNOWN truth
5. FALSE truth
6. NOT_APPLICABLE with proven negated antecedent
7. NOT_APPLICABLE without sufficient evidence
8. valid OR alternative where one branch passes
9. OR alternatives where all branches fail
10. OR alternatives containing unresolved branches
11. empty quantified domain where the domain is proven complete
12. empty quantified domain where completeness is unknown


## Required Adversarial Examples

The final semantics must correctly handle:

### Unknown type

A component exists but its engineering type cannot be mapped to the catalog.

### Missing relationship

A shaft exists but support relationships are incomplete or unknown.

### Whole subsystem deletion

A mission requires controlled rotary output but the candidate contains no
drive subsystem.

### Uncovered interface

A required interface exists but the rule catalog has no validation knowledge
for it.

### Classification dependency

A component may be type A or type B and the unresolved classification changes
which rules apply.

### Valid alternative

The requirement permits strategy A OR strategy B and strategy B is proven
valid.

### Partial design

The candidate is explicitly declared an incomplete intermediate design rather
than the final design of record.


## CAD Rule

Define a precise gating rule for when an engineering result may create a CAD
obligation.

No unresolved relationship, uncovered rule, or incomplete required scope may
silently become concrete geometry.


## Minimal Data Structures

End with concrete suggested data structures for v0.1.

At minimum address whether OMNI needs concepts equivalent to:

- Requirement
- ScopeDeclaration
- Rule
- RuleBinding
- Evaluation
- Dependency
- Finding
- CADObligation
- Provenance

Do not implement them.


## Convergence Requirement

Do not introduce new architectural topics.

Challenge the other agent only on logical inconsistencies, unsafe PASS
conditions, or unnecessary complexity.

If the competing proposal can be made correct through a small refinement,
prefer convergence and state the shared model rather than inventing another
architectural disagreement.

The final result must be specific enough to freeze into a TestCube
implementation specification.
