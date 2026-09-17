# OMNI Frontier Continuation Mission
## Component Intelligence v0.1 — Obligation and Evaluation Semantics

### Prior Research

This is a continuation of:

    OMNI-FRONTIER-0003

Before forming a new hypothesis, inspect the archived research from that thread,
especially:

    .omni-lab/experiments/OMNI-FRONTIER-0003/messages.jsonl
    .omni-lab/experiments/OMNI-FRONTIER-0003/hypothesis.md
    .omni-lab/experiments/OMNI-FRONTIER-0003/conclusion.md
    .omni-lab/experiments/OMNI-FRONTIER-0003/results.json

Treat those artifacts as prior research evidence, not as unquestionable truth.

Do not restart the broad Component Intelligence architecture debate unless a
specific contradiction requires it.

The previous run narrowed the problem substantially but did not converge.


## Current Working Direction

The previous research produced an emerging two-source model:

1. Candidate-independent mission or engineering requirement anchors.

   These must be capable of detecting deletion of an entire required subsystem.

2. Candidate-independent, versioned type/rule knowledge applied conditionally
   to the components and design choices present in a candidate.

   These must be capable of detecting obligations introduced by choices such as
   bearings, belt drives, leadscrews, couplings, or other component families.

The candidate assembly graph supplies design facts and relationships but must
not be allowed to define away the requirements against which it is judged.

This is a working hypothesis, not an established conclusion.


## Research Objective

Resolve the formal evaluation semantics needed so Component Intelligence cannot
produce a vacuous PASS, false FAIL, or fabricated certainty.

The output must be concrete enough to become part of a frozen TestCube
implementation specification.


## Questions That Must Be Resolved

### 1. Obligation Sources

Specify precisely how these interact:

- externally anchored mission/engineering requirements
- type-conditioned engineering rules
- assembly-pattern rules
- candidate component/interface relationships
- explicit user-provided requirements

Determine which sources are authoritative, which are evidence, and which can
create new obligations.


### 2. Missing Subsystems

Define semantics for cases such as:

mission requires controlled rotary output

candidate contains:
    no motor
    no output shaft
    no transmission

The system must not PASS simply because there are no component relationships to
validate.

Specify whether this is FAIL or UNKNOWN and what evidence/completeness
declaration controls that distinction.


### 3. Design-Induced Obligations

Define semantics for cases where the candidate selects a design strategy that
creates additional requirements.

Examples:

candidate selects bearing
    -> bearing support/retention/interface obligations arise

candidate selects belt drive
    -> tensioning/alignment obligations arise

candidate selects leadscrew
    -> support/nut/alignment obligations arise

Explain where these rules live and how they are versioned/provenanced.


### 4. Logical Composition

Resolve the minimum logical operators needed for v0.1.

The architecture must represent requirements such as:

A AND B

A OR B

at least one of A/B/C

all selected bearings must satisfy condition X

if component type T is selected, requirement R applies

exactly one strategy from an allowed set

zero or more optional relationships

required cardinality or bounded cardinality

Do not assume that an AND/OR tree is automatically the best representation.

Compare plausible representations and recommend the simplest one that is
deterministic, inspectable, extensible, and testable.


### 5. Three/Four-Valued Evaluation

The mission requires at least:

PASS
WARN
FAIL
UNKNOWN

Define deterministic combination semantics.

Specifically resolve:

- UNKNOWN AND PASS
- UNKNOWN AND FAIL
- UNKNOWN OR PASS
- UNKNOWN OR FAIL
- alternatives where one strategy is proven valid
- alternatives where no strategy is instantiated
- incomplete evidence
- incomplete rule coverage

UNKNOWN must never silently become PASS.


### 6. Vacuous Satisfaction

Define how OMNI prevents statements like:

"all bearings satisfy the bearing rule"

from producing PASS when the design contains zero bearings but the engineering
requirements require a supported rotating shaft.

Separate logical truth from engineering requirement satisfaction where
necessary.


### 7. Completeness

Determine how OMNI knows whether its rule set is sufficiently complete to emit
PASS rather than UNKNOWN.

Address:

- missing property values
- missing relationship information
- missing rule coverage
- unknown component types
- unsupported assembly patterns
- requirements that cannot be mapped to a known validation strategy

A PASS should mean the relevant required checks were actually covered, not
merely that no detector emitted FAIL.


### 8. CAD Boundary

Determine exactly when Component Intelligence may emit a CAD obligation.

Examples:

bearing seat
housing bore
retaining groove
motor mount
belt tensioning feature
tool-access clearance

Unresolved or UNKNOWN mechanical relationships must not silently become
plausible geometry.

Define what information Oli may consume and what must block or qualify CAD
generation.


### 9. Provenance

Specify how provenance attaches to:

- engineering requirements
- type rules
- component facts
- relationships
- derived obligations
- findings
- CAD obligations

Agreement between Claude and Codex is not engineering provenance.


### 10. Minimal v0.1

End with a concrete recommendation for the smallest implementation that can
prove the architecture.

Specify:

- core schemas
- rule representation
- evaluator
- module boundaries
- initial assembly patterns
- seed component families
- deterministic tests

Do not implement the subsystem during this research shift.


## Required Adversarial Cases

The proposed semantics should correctly classify at least:

1. Entire required drive subsystem deleted.
2. Rotating shaft exists but has no support.
3. Bearing exists but required speed rating is unavailable.
4. Bearing bore mismatches shaft seat diameter.
5. Belt drive has no tensioning strategy.
6. Valid alternative architecture satisfies one of several allowed strategies.
7. Candidate contains an unknown component type.
8. Rule catalog has no coverage for a required interface.
9. Optional component is absent.
10. Candidate deletes a component and thereby deletes the only rule that would
    have checked it.


## Desired Conclusion

Produce a concrete architecture recommendation that resolves the remaining
disagreement from OMNI-FRONTIER-0003.

The conclusion should specify:

- obligation-generation semantics
- logical/quantifier semantics
- completeness semantics
- PASS/WARN/FAIL/UNKNOWN combination rules
- provenance
- CAD gating
- minimal module/schema design
- deterministic TestCube acceptance tests

The result should be specific enough that it can be frozen and independently
implemented by two isolated TestCube candidates.
