# TestCube trusted structured-edit transport

Implementation checkpoint for independent Claude review, starting at
`700ccc59beac0a340b0ca921645d530c6f4a99c7`. No live provider invocation, new
trial, promotion, retry, collector change or arbiter change belongs to this
milestone. The change to the model boundary is intentional: models propose
source replacements; trusted Git produces transport syntax. This removes the
manual unified-diff arithmetic that prevented Trial 0002 from reaching collection.

## Historical evidence

The external archives at `/home/honri/omni_testcube_trials` remain unchanged.
[Historical integrity inventory](testcube_historical_integrity.json) records
every existing file's SHA-256, captured before implementation and compared
afterward, without copying raw model output or credential material into docs.

```text
OMNI-TESTCUBE-TRIAL-0001
GENERATION_FAILED
reason: Codex startup/runtime state

OMNI-TESTCUBE-TRIAL-0002
GENERATION_FAILED
reason: Claude malformed unified diff
```

Trial 0002's existing evidence is preserved: dual preflight passed; Claude
made one generation call and returned strict candidate JSON containing a
structurally malformed patch (`git apply --numstat`: corrupt patch); Codex
made one generation call and its patch parsed. Collector was NOT_REACHED,
arbiter NOT_AVAILABLE, trusted OMNI UNCHANGED. These remain historical
failures; the synthetic regression does not reinterpret either outcome.

## Contract and authority

`candidate-edit.v1` is the default supervised library/CLI transport. The old
`candidate.v1` requires explicit version selection for compatibility. The fake
CLI permits that selection; the live CLI selects only structured edits. A
single provider invocation cannot select or mix transports.

The strict schema requires exactly `schema_version`, `summary`, `edits`,
`assumptions`, and `limitations`. Each edit requires exactly `path`, `before`,
and `after`. Duplicate JSON keys, nonfinite numbers (including exponent
overflow), unexpected types/fields, missing fields, NULs and invalid Unicode
fail closed. Audit prose has no evidentiary or winner authority.

Provider identity is fixed externally: Claude/A, Codex/B. The generation
record binds trial/task ID and digest, resolved immutable base, provider and
version, slot, transport, canonical proposal hash/size, and patch hash/size.
The manifest binds that record and the artifacts; the externally retained
receipt binds the manifest. Neither model can write published artifacts.
Proposal edits sort by `(path, before, after)` before audit serialization.
Original JSON order remains available in the existing raw stdout artifact.

Before rendering, paths independently pass exact repository-relative syntax,
TaskSpec allowed/forbidden paths, CollectorPolicy allowed/forbidden paths,
validation exclusion, FIRST_TRIAL_FORBIDDEN and protected-path checks. No
absolute/traversal/normalized aliases, globs, new files, symlinks, submodules,
renames, deletions or mode operations are representable as accepted edits.
The contract supports 1–3 existing Python files, up to the human's lower bound.

## Deterministic rendering

The harness resolves the human base once. Its trusted source must be clean,
HEAD must equal that full commit, and existing source-integrity/index-flag
checks must pass. The renderer checks the supplied integrity snapshot again.
It clones without local object sharing or hardlinks into a private disposable
repository, removes its remote, and detaches at the immutable base. Git hooks,
global/system configuration, external diff and textconv are disabled through
the existing trusted Git wrapper and explicit diff flags.

Edited sources must be bounded regular UTF-8 files with LF newlines, no BOM,
no NUL, no non-UTF-8 Python encoding declaration and no Git attributes on the
edited path. CRLF, mixed/CR newlines and attribute-driven transforms fail
closed. Raw checkout content is hashed with `hash-object --no-filters` and
compared to the pinned Git blob before replacement.

Each `before` must occur exactly once, counting even self-overlapping matches.
All byte ranges refer to the original base source; duplicate entries and any
intersecting ranges are rejected. Valid replacements apply from highest byte
offset to lowest. Byte reads/writes preserve all bytes outside those regions,
including tabs, trailing spaces, non-ASCII UTF-8 and missing final newlines.
An unchanged plan is rejected. Result encoding/newline restrictions are
checked again; existing executable bits are preserved.

Git writes the authoritative patch directly to a disposable file, avoiding
stdout decoding. Flags fix full blob hashes, Myers diff without indentation
heuristics, three context lines, no renames/color/external diff/textconv, and
explicit `a/` and `b/` prefixes. Python never constructs hunk syntax.

A second fresh pinned-base copy must accept the exact patch using
`git apply --index --binary --whitespace=nowarn`. The renderer compares applied
bytes and modes to its expected replacements, and derives staged changes
through the existing collector scope helpers. Actual paths must match the
planned files, contain only modifications and meet the human path/file/line
bounds. Git/I/O failure or inconsistent rendered/re-applied output is a
`RENDERER_FAILURE`; an unsupported proposal or exceeded policy bound is
`INVALID_OUTPUT`. Both stop generation before collection. Disposable renderer
copies live outside the trial archive, under the provider-masked output root,
and are removed on exit. Even a cleanup failure cannot sweep a renderer
checkout into the archive; only normal Git observations are retained.

Bounds: 128 KiB raw JSON including provider envelope, 128 KiB canonical
proposal, 16 edits, 16 KiB per before/after, 64 KiB aggregate per side, 1 MiB
per base file. Rendered bytes obey the existing `max_patch_bytes` (at most
128 KiB), at most 3 touched files and 100 changed lines or lower human limits.

## Publication, collection and limitations

Trusted harness code alone writes `generation/candidate-{A,B}/proposal.json`
and `patch.diff`, after provider exit. Both hashes and sizes are checked
before handoff and when verifying a completed receipt. The unchanged collector
receives only patch files, independently derives scope and runs isolated
commands to create CandidateEvidence. Generation/collector patch hashes and
base must agree. The unchanged deterministic arbiter alone determines the
verdict. Both generations must succeed before any collection; retries remain
zero and candidate generation calls remain at most one per provider.

Claude still receives Read/Grep/Glob only. Codex retains read-only sandboxing
and its reviewed private ephemeral CODEX_HOME. Provider mount/state logic is
unchanged; schema and prompt selection are the only provider adaptations.
Native fake CLI tests exercise both transport versions through those mounts.
Neither provider receives or writes a renderer repository.

The existing secret limitation remains: raw generation stdout can contain
deliberately echoed readable credentials. This transport is not a secret
scrubber; accepted model strings may contain deliberately echoed material.
New proposal/render code never reads auth.json or Claude credential files,
serializes the environment, or copies provider stderr into manifests.
Synthetic sentinel tests cover accidental environment/stderr copying. The
operator, host, trusted runtime and Git remain trusted as before.

## Verification and handoff

`tests/test_testcube_edit_transport.py` covers strict JSON and byte bounds,
exact/ambiguous/self-overlapping matches, duplicate/overlapping edits, reversed
order, path guards, unsupported file/encoding/newline/attribute forms, mode
preservation, fresh application and byte equality. It exercises all four A/B
behavioral outcomes through real collection, isolated tests and arbitration.
Invalid generation formats stop before collection; injected Git application
failure is distinctly classified as renderer failure. Proposal tampering is
rejected before collection.

The Trial 0002 regression uses an inert memory-manager fixture and the two
historical replacement semantics: guard mission slicing and seed slicing with
`if n > 0 else []`. Both fake models emit structured edits. Trusted Git emits
correct hashes and hunk counts, both patches parse and execute in collection,
and tests cover positive, zero and negative requests. No historical file is
modified or used as writable test input.

Existing legacy fake tests explicitly select their old schema; native fake
Claude/Codex tests additionally cover the new transport. No real model or
provider authentication is called. Test results and final checkpoint are
reported in the implementation handoff to the human; this document is not an
independent approval. Independent Claude review is required before Trial 0003.
Autonomous scheduled GitHub issue execution remains unavailable.

Observed validation for this implementation (all real provider/model calls: 0):

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_testcube_candidate_harness.py tests/test_testcube_edit_transport.py -q
171 passed in 87.33s

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_testcube_collector.py tests/test_testcube_arbiter.py tests/test_frontier_claude_provider.py tests/test_frontier_codex_provider.py tests/test_sandbox*.py -q
668 passed in 54.44s

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests -q
3387 passed, 2 warnings in 156.18s
```

The passing runs used execution permission outside the outer Codex sandbox;
the tests' actual Bubblewrap boundaries remained enabled. The initial
restricted run could not complete collector namespace setup. The full suite's
two warnings concern existing Python 3.10/Google library support and deprecated
`google.generativeai`; no dependency changes were made.
