# Component Intelligence v0.1 — human-owned validation adapter

## Authority and purpose

This interface exists only to make competing implementations comparable.
[`../frozen_testcube_spec.md`](../frozen_testcube_spec.md) remains the semantic
authority, with SHA-256:

```text
8c7f5a5f61feb2288229925323c63664c0a4ee756886068d46b87877cd947115
```

This document specifies a **test adapter**, not a redesign of the frozen
architecture. Candidate classes, file layout, catalogs, storage, dependency
representation, and algorithms are not prescribed. An implementation may
translate these wire documents into any internal representation consistent
with the frozen specification. No production implementation is supplied here.

All files in this directory are human-owned, pinned-baseline validation files.
Candidates may read them but **cannot modify them**. The human task must list
this directory as forbidden and pin the specification and validation files as
trusted validation paths. These tests operationalize the frozen test
requirements in the human baseline; candidate-authored changes to these tests
are not permitted.

Passing is evidence of conformance to this frozen implementation hypothesis,
not universal mechanical-engineering validation, a safety certification, or
permission to merge, promote, deploy, or release a real machine.

## Public entry points

The candidate package `omni.component_intelligence` exposes these two public
evaluation callables:

```python
evaluate_contract(document: dict) -> dict
evaluate_assembly(document: dict) -> dict
```

No other callable is required by this adapter. Inputs and outputs contain only
JSON objects with string keys, arrays, strings, finite numbers, booleans, and
null. Outputs must be dictionaries, not custom implementation objects. Inputs
must not be mutated. Calls are deterministic and have no network, filesystem
write, subprocess, model, or external-service effects.

Fixture names, scenario numbers, and expected answers are not passed to either
function. IDs are opaque references, never dispatch keys for special-case
answers. Dictionary insertion order and component/requirement/fact/completion
list order do not change semantics. Each input is evaluated twice; identical
inputs must produce identical canonical JSON, including finding IDs and list
ordering. Internal object identity is irrelevant.

## Shared envelope and result

Both input documents have:

- `revision`: `FINAL` or `INTERMEDIATE`;
- `revision_id`: inert revision identity, never evidence of scope closure;
- `scopes`: map of scope ID to `CLOSED` or `OPEN`;
- `required_scopes`: IDs whose closure is necessary for overall release;
- `dependencies`: domain declarations described below;
- `completions`: the explicitly admitted joint worlds;
- `requirements`: the human-owned instantiated contract, independent of the
  presence of components or relationships.

Both results contain:

```json
{
  "verdict": "PASS",
  "requirement_results": {
    "opaque-human-requirement-id": {
      "applicability": "APPLIES",
      "truth": "TRUE",
      "coverage": "COVERED",
      "scope": "CLOSED",
      "dependency_ids": [],
      "completion_results": {
        "base": {"applicability": "APPLIES", "truth": "TRUE", "coverage": "COVERED"}
      }
    }
  },
  "findings": []
}
```

Allowed verdicts are `PASS`, `WARN`, `FAIL`, `UNKNOWN`. Applicability is
`APPLIES`, `NOT_APPLICABLE`, or `UNDETERMINED`; truth is `TRUE`, `FALSE`, or
`UNKNOWN`; coverage is `COVERED`, `UNCOVERED`, or `UNKNOWN`. The result must
retain exactly the human requirement IDs, including excluded requirements.
Internal pattern subrules may appear in findings, but may not replace, erase,
or add human requirements to this result map. `scope` summarizes the
requirement's `required_scopes` (OPEN if any is OPEN).

Each requirement result must retain every input completion ID exactly once,
with its corresponding applicability/truth/coverage together. The
`dependency_ids` list is the sorted, unique union of that requirement's declared
and expression/antecedent dependency references. These are references to the
input declarations, not independently inferred domains. Input completion IDs
must not be dropped or expanded into invented Cartesian combinations.

Extra diagnostic result fields are allowed, but cannot alter these fields or
substitute for them. CAD dimensions have a stricter contract below.

## `evaluate_contract`: already-instantiated logical observations

A logical requirement has:

```json
{
  "id": "support-must-exist",
  "mandatory": true,
  "antecedent": {"op": "literal", "truth": "TRUE"},
  "predicate": {"op": "exists", "scope": "relationships", "items": []},
  "required_scopes": ["relationships"],
  "dependency_ids": [],
  "provenance": {"category": "USER_PROVIDED", "origin": "HUMAN", "source_ref": "validation:generic-v01"}
}
```

The following expression syntax belongs only to the adapter. Candidates need
not use an expression tree internally:

| Form | Fields and meaning |
| --- | --- |
| `literal` | `truth`: one of TRUE/FALSE/UNKNOWN; coverage is COVERED because the adapter supplies the logical observation directly. |
| `observation` | `dependency_ids`, `by_completion`: map from each admitted completion ID to one `{truth, coverage}` pair. |
| `and`, `or` | Nonempty `args` array of expressions, evaluated within each completion before aggregation. |
| `forall`, `exists` | `scope` ID and `items` array of instantiated expressions over that domain. |
| `cardinality` | `scope`, `items`, integer `min`, and integer-or-null `max` (`null` means no upper bound). Counts TRUE members, not raw list length. |

`and` is FALSE if any operand is FALSE, TRUE if all are TRUE, otherwise UNKNOWN.
`or` is TRUE if any operand is TRUE, FALSE if all are FALSE, otherwise UNKNOWN.
This gives ordinary three-valued A AND B, A OR B, and at-least-one semantics.

Coverage remains separate. For conjunction, universal, and cardinality nodes,
coverage is COVERED when all instantiated child checks are COVERED; otherwise
UNCOVERED if any is UNCOVERED; otherwise UNKNOWN. Empty instantiated child
lists have COVERED logical coverage: the closure declaration supports the
empty-domain inference. This does not establish a separate existence claim.

For a TRUE disjunction/existential, only TRUE witnesses can establish its
coverage: any TRUE+COVERED witness makes it COVERED; otherwise a TRUE+UNKNOWN
witness makes coverage UNKNOWN; otherwise it is UNCOVERED. A FALSE+COVERED
alternative cannot cover an incompatible TRUE+UNCOVERED alternative. For a
non-TRUE disjunction/existential, use the all-child coverage rule above.

For a CLOSED domain, a universal is the conjunction and an existential the
disjunction of its items. Thus a closed empty universal is TRUE; a closed empty
existential is FALSE. For OPEN domains, an observed FALSE can disprove a
universal and an observed TRUE can witness an existential; otherwise
completeness-dependent truth is UNKNOWN. Required OPEN scope still prevents
PASS even when an existential already has a valid witness.

For cardinality, known TRUE items give a lower count, and TRUE plus UNKNOWN
items give an upper count. An OPEN domain has an unresolved upper count. TRUE
requires all admitted counts to satisfy the bounds; FALSE means all violate
at least one bound; otherwise UNKNOWN. This represents required cardinality,
bounded cardinality, optional membership (`min=0, max=1`), and mutually
exclusive strategies (`min=1, max=1`). An OPEN domain cannot hide an already
observed excess over `max`.

### Applicability and conditional requirements

The requirement's antecedent provides conditional semantics. Within one
completion, a covered TRUE antecedent yields APPLIES; a covered FALSE
antecedent yields NOT_APPLICABLE; insufficient evidence yields UNDETERMINED.
NOT_APPLICABLE must have an explanatory finding grounded in the false
antecedent. Missing information is not false evidence.

When applicability is not APPLIES, expose consequent truth as UNKNOWN (not
executed/proven for this conditional obligation), retaining applicability
separately. Coverage still describes available validation knowledge; the
covered literal antecedents in the fixtures have COVERED validation. Excluded
requirements do not generate mandatory FALSE. All mandatory requirements being
excluded is an UNKNOWN contract, not PASS.

### Finite, joint and unresolved domains

For example:

```json
{
  "dependencies": [{
    "id": "classification",
    "kind": "JOINT",
    "members": ["type", "rule"],
    "options": [
      {"id": "A", "values": {"type": "A", "rule": "rule-A"}},
      {"id": "B", "values": {"type": "B", "rule": "rule-B"}}
    ]
  }],
  "completions": [
    {"id": "case-A", "choices": {"classification": "A"}},
    {"id": "case-B", "choices": {"classification": "B"}}
  ]
}
```

`FINITE` uses one member; `JOINT` binds several members into each indivisible
option. `completions` is the complete admitted set for bounded resolved domains;
it is not an instruction to independently expand each member. An ordinary
fully instantiated document has `[ {"id": "base", "choices": {}} ]`.

`UNBOUNDED`, or a FINITE declaration with no enumerated options, represents
unresolved information. It is not an empty logical quantifier domain. A
requirement referencing such a dependency cannot establish TRUE, even if a
placeholder observation/literal says TRUE. Its truth is UNKNOWN and a finding
must name the unresolved dependency. An unresolved antecedent dependency makes
applicability UNDETERMINED. Unrelated dependencies do not automatically poison
requirements that do not reference them.

For a requirement applicable in every admitted completion: all TRUE gives
aggregate TRUE, all FALSE gives aggregate FALSE, disagreement gives UNKNOWN.
Coverage is its common value if all completions agree, otherwise UNKNOWN.
All NOT_APPLICABLE gives NOT_APPLICABLE; mixed/unknown applicability gives
UNDETERMINED and aggregate truth UNKNOWN. Proof by a correlated compound
expression is performed inside each completion first: `(A AND B)` can be
FALSE in every completion even when A and B individually aggregate UNKNOWN.

The crossed-completion fixture has a different TRUE+UNCOVERED alternative in
each world and an incompatible FALSE+COVERED alternative. Truth is TRUE in each
world, but coverage is UNCOVERED in each world. Combining truth from one world
with coverage from another must never manufacture PASS.

## Overall verdict ordering

1. Any applicable mandatory requirement proven FALSE gives FAIL, even when
   other requirements, scope, or revision are unresolved.
2. Otherwise, any mandatory UNDETERMINED applicability, UNKNOWN truth,
   UNCOVERED/UNKNOWN validation, unresolved required dependency, required OPEN
   scope, INTERMEDIATE revision, or empty/entirely excluded mandatory contract
   gives UNKNOWN.
3. Otherwise, an applicable advisory condition not fully TRUE gives WARN.
4. Otherwise PASS.

There are no waivers. Required global scopes and applicable mandatory local
scopes must be CLOSED. Logical vacuity cannot satisfy an independent mandatory
existence requirement. No observed FAIL is insufficient for PASS.

## `evaluate_assembly`: mechanical wire model

In addition to the shared envelope, inputs contain `components`, `interfaces`,
`relationships`, `patterns`, and `cad_requests` arrays. IDs are unique within
an entity kind; all references are explicit. Fixtures deliberately keep a
missing target's ID in human requirements/pattern roles to test existence.

A component has `id`, `family`, `subtype`, `facts` (a map of property name to
EngineeringFact), and `provenance`. Fact property names have engineering
meaning; fact IDs and component IDs do not. Supported synthetic adapter pairs
include:

| Family | Subtypes used |
| --- | --- |
| `fastener` | `bolt`, `retaining_ring` |
| `shaft` | `round_shaft` |
| `bearing` | `radial_bearing` |
| `coupling` | `rigid_coupling` |
| `transmission` | `spur_gear`, `pulley`, `belt` |
| `motor` | `rotary_motor` |
| `linear_motion` | `leadscrew`, `nut`, `carriage`, `linear_guide`, `tensioner` |
| `structure` | `housing` |

These are generic adapter records, not an exhaustive catalog or a prescription
for the candidate's seed storage. Unmapped families/subtypes produce UNKNOWN
with an explicit type/coverage finding, never generic compatibility PASS.

EngineeringFacts have:

```json
{
  "id": "shaft-diameter",
  "value": 10,
  "units": "mm",
  "epistemic": "KNOWN",
  "provenance": {"category": "USER_PROVIDED", "origin": "HUMAN", "source_ref": "validation:generic-v01"}
}
```

UNKNOWN uses `value: null` and must stay UNKNOWN/null. An omitted fact is
missing evidence, not a zero-valued fact to invent. ASSUMED retains its proposed
value and epistemic label. In this adapter's deterministic numeric checks,
only KNOWN values establish compatibility/capability; ASSUMED inputs leave the
result UNKNOWN with an assumption finding. This conservative interpretation
makes the otherwise unspecified use of assumptions explicit without conflating
ASSUMED and KNOWN. Fixtures use mm, rpm, or null units for booleans. They require
no invented commercial rating, tolerance, fit class, or unit conversion.

Provenance categories are STANDARD, MANUFACTURER, HANDBOOK, OMNI_VALIDATED,
OMNI_HEURISTIC, USER_PROVIDED. Labels in synthetic fixtures are representation
tests, not assertions that a real standard/manufacturer supplied these values.
`origin` is HUMAN or MODEL; `source_ref` is preserved. `agreement_count` is
inert metadata, never a trust upgrade. A MODEL-origin claim of trusted
STANDARD/MANUFACTURER/HANDBOOK/OMNI_VALIDATED provenance must not be accepted as
KNOWN. The adapter expects UNKNOWN evaluation and an UNTRUSTED_PROVENANCE
finding. It permits reporting the value as ASSUMED (preserving the proposal)
or UNKNOWN/null, with MODEL origin retained and a nontrusted category
(OMNI_HEURISTIC or USER_PROVIDED). No fixed internal sanitization algorithm is
required.

Assembly output also includes `fact_results`, a map by fact ID. It preserves
all input fact fields and provenance except for the explicitly rejected model
trust claims above. Omitted facts must not appear as invented fact records.
This projection makes epistemic/provenance handling inspectable without
requiring access to candidate internals.

### Interfaces, relationships and requirements

An interface has `id`, `kind`, `participants` (component IDs), `dimensions`
(map of dimension role to fact ID), and provenance. The fixtures use
`shaft_to_bearing` (`shaft_diameter`, `bearing_bore`) and `shaft_to_coupling`
(`shaft_diameter`, `coupling_bore`). Dimensions reference component facts.

A relationship has `id`, `kind`, `source`, `target`, optional/null `interface`,
and provenance. Direction matters. All endpoints must exist to establish a
relationship. Absent required edges in a CLOSED scope are FALSE; when scope
is OPEN and the edge could still exist, the result is UNKNOWN. Present valid
edges may establish TRUE while OPEN scope still blocks release.

An assembly requirement replaces `predicate` with `rule`, `parameters`, and
`coverage`; other requirement fields are unchanged. `coverage` is the human's
availability declaration for this trial. It may restrict available validation;
it cannot turn an unknown rule/type into known coverage. When validation is
UNCOVERED/UNKNOWN, engineering truth from that unavailable rule is UNKNOWN.
This differs from `evaluate_contract`, whose independently supplied truth
observations can already be known despite a separate coverage gap.

Assembly antecedents accept the logical forms above and
`{"op":"fact", "fact_id":"shaft-rotating"}` for a KNOWN boolean fact.
Unknown, assumed, omitted, or invalid boolean evidence gives UNKNOWN antecedent
truth and UNDETERMINED applicability, not NOT_APPLICABLE.

| Adapter rule | Parameters and tested behavior |
| --- | --- |
| `shaft_bearing_bore` | `interface`: exact equality of its two KNOWN nominal mm dimensions; known mismatch FALSE, missing/unknown dimensions UNKNOWN. |
| `shaft_coupling_bore` | `interface`: analogous nominal equality. |
| `shaft_support` | `shaft`: an existing shaft requires a `supports` edge from an existing bearing/support. |
| `shaft_retention` | `shaft`: requires a `retains` edge from an existing retention component. |
| `bearing_speed` | `shaft`, `bearing`: KNOWN shaft `speed` must be <= KNOWN bearing `speed_rating` in rpm. Missing/UNKNOWN/ASSUMED rating is UNKNOWN, even when requested speed is zero. |
| `component_type` | `component`: existing supported family/subtype TRUE; existing unknown type UNKNOWN/UNCOVERED; absent component in CLOSED inventory FALSE. |
| `component_exists` | `family`, `minimum`: independent minimum existence requirement; CLOSED insufficient inventory FALSE. |
| `pattern` | `pattern`: evaluate the explicitly supplied pattern roles and edges below. |

Missing mandatory referenced components in CLOSED inventory give FALSE for
existence, interface, support/retention, and pattern requirements. A numerical
capability check without its referenced facts remains UNKNOWN. Unknown rule
names give UNKNOWN/UNCOVERED, even if the input requested COVERED. These rules
are adapter dispatch names; candidate rule classes/identifiers remain free.
Additional catalog knowledge must not override human scope or coverage masks.

Nominal equality is a deliberately small synthetic rule. It is not a real
bearing-fit, tolerance, rating, load-capacity, or safety certification.

### Assembly patterns

Patterns have `id`, `kind`, `roles` (role name to component ID), and provenance.
A pattern is evaluated when a human requirement references it. Merely naming a
pattern cannot produce PASS. Its declared components and these directed edges
must exist, with the corresponding generic types:

| Pattern | Required role edges (`source -kind-> target`) |
| --- | --- |
| `supported_shaft` | support -supports-> shaft; structure -houses-> support; retainer -retains-> shaft when the retainer role is declared |
| `motor_to_shaft` | motor -drives-> coupling; coupling -drives-> shaft; support -supports-> shaft; structure -houses-> support; shaft -drives-> load |
| `motor_to_leadscrew_stage` | motor -drives-> coupling; coupling -drives-> leadscrew; support -supports-> leadscrew; leadscrew -drives-> nut; nut -attached_to-> carriage; guide -guides-> carriage |
| `belt_drive` | motor -drives-> pulley; pulley -drives-> belt; belt -drives-> driven_pulley; driven_pulley -drives-> shaft; support -supports-> shaft; tensioner -tensions-> belt |
| `geared_output` | motor -drives-> gear; gear -drives-> shaft; support -supports-> shaft; shaft -drives-> load |

The human contract may express permitted alternatives through logical OR,
cardinality, or distinct pattern requirements. This fixture's tensioner role
is a generic explicit tensioning strategy, not a demand for a particular
commercial tensioning device. Deleting candidate objects/relationships cannot
delete the separate human requirement or its expected result.

## Findings

Findings are a list of objects containing:

- unique stable `id`, `requirement_id`, `rule_id`, `code`, `state`;
- `components` and `interfaces` reference arrays (possibly empty);
- nonempty structured `observed` and `expected` objects;
- nonempty `explanation` (wording is not compared);
- nonempty `provenance` array of provenance records;
- `dependency_ids` array, naming unresolved dependencies where relevant.

Every non-TRUE, non-COVERED, OPEN, excluded, or undetermined requirement must
have an explanation. Tests also look for stable reason codes where the cause
is known: MISSING_COMPONENT, MISSING_RELATIONSHIP, MISSING_FACT, ASSUMED_FACT,
DIMENSION_MISMATCH, UNKNOWN_COMPONENT_TYPE, UNCOVERED_RULE, OPEN_SCOPE,
UNRESOLVED_DEPENDENCY, UNDETERMINED_APPLICABILITY, NOT_APPLICABLE,
UNTRUSTED_PROVENANCE. Additional findings/codes are allowed. Internal `rule_id`
names and finding prose are not prescribed. References to absent components
are legitimate when the human requirement still names those components.

Where observed fact values are requested, use `observed: {fact_id: fact}` with
full epistemic/provenance metadata, or `{"missing_fact": fact_id}` for an
omitted fact. This makes absence, UNKNOWN, ASSUMED, and numeric zero separable.

## CAD request and obligation adapter

A human request has:

```json
{
  "id": "seat-feature",
  "target": "shaft",
  "feature": "bearing_seat",
  "dimension_inputs": {"diameter": "shaft-diameter"},
  "prerequisites": ["bore", "support-required"],
  "provenance": {"category": "USER_PROVIDED", "origin": "HUMAN", "source_ref": "validation:generic-v01"}
}
```

Assembly results contain one `cad_obligations` entry per request, with the
same `id`, `target`, `feature`, and:

- `status`: RELEASED or BLOCKED;
- `known_dimensions`: dimension role to `{value, units, fact_id}`;
- `unresolved_inputs`: references to blocking requirement/fact/dependency IDs,
  `scope:<scope-id>`, or `revision` as applicable;
- nonempty `provenance` list;
- `source_requirements`: the request's prerequisite IDs;
- `source_rules`: their adapter rule names.

A request is RELEASED only when its prerequisites are APPLIES/TRUE/COVERED,
their required scopes and required global scopes are CLOSED, referenced
required dependencies are resolved, required numeric dimensions are KNOWN,
and the revision is FINAL. When these conditions are fully met, the explicit
positive fixture requires RELEASED with the justified known dimensions. This
checks useful release behavior rather than accepting perpetual BLOCKED output.
No actual CAD kernel, mesh, solid, or Oli invocation is required.

Otherwise emit BLOCKED, retaining inspectable known dimensions and explaining
the blockers. Unknown dimensions must be omitted from `known_dimensions`,
never filled with zero or another default. No unrequested dimension or
fabricated value is allowed. A blocked request cannot silently disappear.
A request's prerequisites are local: a separate failed requirement unrelated
to that request does not erase otherwise justified dimensions or force an
unrelated CAD request to BLOCKED. Overall assembly release still fails.

This adapter intentionally extends the conservative CAD gate to FINAL revision
and explicitly requested numeric dimensions. It does not introduce waivers or
permit unresolved geometry. CAD provenance must reference the actual input
facts and governing requirements/rules.

## Scenario and metamorphic coverage

`fixtures_v01.py` holds the human-owned documents and explicit expected
outcomes. It is fixture data, not a reference production evaluator. The suite
includes all seventeen frozen scenarios:

1. complete drive absence with human requirements retained;
2. unsupported shaft with CLOSED relationship inventory;
3. unknown/omitted bearing rating, including requested speed zero;
4. known shaft/bearing bore mismatch;
5. closed belt drive without tensioning;
6. fully valid OR alternative B;
7. unknown subtype/family with explicit coverage finding;
8. unavailable or unregistered mandatory rule;
9. optional absence through bounded cardinality;
10. deleted objects/patterns with independent mission existence requirement;
11. shared finite/joint classification across multiple requirements;
12. OPEN relevant inventory despite no observed defect;
13. closed empty existential;
14. vacuous universal plus a separate failing existence requirement;
15. unresolved CAD dimension and each release-blocking axis;
16. positive FINAL assembly and released, justified CAD obligation;
17. incompatible truth/coverage witnesses in correlated completions.

Additional tables test truth/coverage combinations, FAIL priority, empty and
excluded contracts, advisory WARN, quantifiers, cardinality and mutual
exclusion, all initial families/patterns, support/retention, coupling mismatch,
all six provenance categories, and multiple model-agreement counts.

Metamorphic fixtures deterministically rename component, interface, fact,
requirement, dependency and completion IDs, reverse collections, and reorder
fact mappings. Type names, role names, fact property names, and rule vocabulary
are deliberately preserved. Other paired fixtures change a known bore
dimension (PASS -> FAIL), KNOWN to UNKNOWN (resolved -> UNKNOWN), and CLOSED to
OPEN (blocks PASS). No random seed, network, model call, or hidden candidate
architecture is needed. Full outputs are checked twice for determinism.

## Commands and baseline expectations

```bash
python experiments/component_intelligence_v01/validation/verify_frozen_spec.py
python experiments/component_intelligence_v01/validation/component_intelligence_validation.py
python experiments/component_intelligence_v01/validation/validation_self_check.py
```

The frozen-spec verifier hashes the original file independently and never
rewrites it. The candidate runner also checks that hash before importing the
candidate API. On the unimplemented baseline, the verifier must PASS and the
candidate runner must exit nonzero with `missing package
omni.component_intelligence` (or missing public callables). That expected
failure is not a broken fixture or missing validator dependency.

The self-check is **not** a candidate acceptance command. It checks fixture
references, scenario coverage, checker shape handling, input preservation,
determinism detection, and rejection of deliberately corrupted canned
responses. Those responses are assembled from the fixed expected answers;
they do not implement requirement or mechanical evaluation. A self-check PASS
is evidence about the validator, not Component Intelligence.

All validator code uses the Python standard library. Entry scripts suppress
bytecode writes; candidate chatter is discarded without file output. A Python
audit guard rejects ordinary Python file mutations, networking, and process
launches during evaluation. This is a defensive check, not a security sandbox
against hostile native code. Future trials must run the explicit candidate
runner under TestCube's existing read-only, network-isolated, bounded trusted
CommandSpec boundary. No validator command launches an LLM or a TestCube trial.

These filenames are intentionally outside ordinary pytest discovery. The
normal OMNI suite must remain green while the candidate package is absent.
