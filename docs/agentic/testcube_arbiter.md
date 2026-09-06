# TestCube deterministic candidate-patch arbiter

**AI proposes. Deterministic code disposes.**

`omni/testcube/` compares two software-patch evidence snapshots under a task's
explicit deterministic policy. It returns a candidate artifact reference for
human review. It does not generate, apply, execute, commit, merge, push, deploy,
delete, or promote patches; fetch issues; open PRs; or schedule work.

Candidate explanations, confidence scores, and model identity are not
arbitration evidence.

Passing the arbiter means a candidate satisfied the configured deterministic
evaluation policy. It does not mean OMNI autonomously merged or deployed the
candidate.

## Architecture and reuse

Inspection at starting checkpoint `40f2c0f` found no TestCube package or
software-patch arbiter, patch-application helper, or worktree-isolation layer.
The relevant existing components are:

- `omni/autodev/`: local issue readiness, protected-path matching, run-directory
  scaffolds, and production packets. TestCube reuses its path normalization and
  literal/prefix/glob matcher. Glob matching now uses `fnmatchcase` so host case
  normalization cannot change the shared POSIX path contract.
- `omni.autodev.packets.TestEvidence`: a mutable command record with outcome,
  exit code, timestamps, and output summary, without test counts. TestCube's
  `CheckEvidence.from_test_evidence` snapshots it, rejects contradictory
  outcome/exit-code pairs, and excludes summary prose and timestamps.
- `agents/candidate_evaluator.py`: a Vega **design** evaluator. Its description
  heuristics, weighted scores, recommendation boost, and order-based tie break
  are unsuitable for software-patch arbitration. It is not changed or imported.
- `backend/app/sandbox/`: command execution and structured command reports,
  including timeout and resource-failure classification. It is not a security
  sandbox and supplies no patch isolation. TestCube adds no execution layer.
- Golden Standard benchmarks validate engineering mission artifacts; they are
  not software performance comparison runners.
- `omni/frontier/`: research messages, safety policy, providers, shift routing,
  and research-specific events. It is not imported or wired to TestCube.
  Mission telemetry writes timestamped files; Frontier events require shift
  state. Neither is used inside this pure decision function. A future caller
  can archive the returned gates, comparisons, and verdict through its existing
  event layer.

The separate frozen command shape is intentional: the legacy record is mutable,
allows contradictory success labels, and cannot carry test counts. Adapting at
this boundary preserves existing packet callers without broad refactoring.

## Inputs and trust boundary

The public seam is:

```python
from omni.testcube import evaluate

result = evaluate(candidate_a=evidence_a, candidate_b=evidence_b, policy=policy)
review_artifact = result.winning_artifact_ref  # None for either non-winning verdict
serialized_result = result.to_json()
```

All inputs are frozen dataclasses with immutable nested tuples. JSON-shaped
records can be reconstructed with `candidate_evidence_from_dict` and
`candidate_policy_from_dict`; unknown fields are rejected. `dataclasses.asdict`
provides the input serialization surface. Results have the schema marker
`omni.testcube.arbitration.v1` and deterministic JSON serialization.

`EvidenceIdentity(evaluation_id, candidate_id, patch_ref)` binds every command
and measurement to one evaluation, one exact slot (`A` or `B`), and one patch
artifact. Nested identities must match the candidate; candidate slots must
match API argument names; evaluation IDs must match the policy. Patch refs and
evidence refs are opaque identifiers: no file is opened or interpreted.

The human-controlled orchestration/collector must own the policy, associate
check IDs with the actual required commands, pin the base revision and patch
artifact, and collect evidence from deterministic tools. It must provide the
complete changed-path inventory (including deleted paths and both sides of a
rename), complete operation/safety audits, and measurements for the same
workload and execution protocol. A candidate agent's claim that a check passed
is not a trusted collector observation.

This phase validates evidence structure and consistency; it does not authenticate
evidence origin, verify artifact hashes, detect omitted files, resolve symlinks,
or prove the declared benchmark protocol was followed. Those collection and
execution responsibilities remain prerequisites for a real candidate trial.

## Mandatory gates

Every candidate requires successful recorded checks with these IDs:

| Check ID | Evidence represented by its command exit code |
| --- | --- |
| `patch.apply` | Patch applies cleanly to the pinned base |
| `git.diff_check` | `git diff --check` succeeds |
| `build` | Required build succeeds |
| `safety` | Configured repository safety/invariant checker succeeds |
| `operations` | Operation audit finds no forbidden operation |
| `test:<group>` | Each `required_test_groups` entry succeeds |
| `validator:<name>` | Each `required_validators` entry succeeds |
| `static:<name>` | Each `required_static_checks` entry (e.g. lint/types) succeeds |

`CheckEvidence` contains the recorded `command`, integer `exit_code`, outcome,
artifact reference, and optional `passed`, `failed`, `skipped`, and
`duration_seconds`. A completed command succeeds only with `exit_code == 0`.
Nonzero exits (including pytest's zero-collection exit 5), timeouts, execution
errors, and missing required checks cannot pass. Timeout/error records have no
exit code; timeouts retain their distinct reason and are not reported as an
ordinary test failure. Counts are observations, not a replacement success
signal; nonzero failed count with exit zero is rejected as contradictory.

All additional supplied checks also gate validity, so a reported regression
failure cannot disappear merely because focused tests passed. Unknown required
validator names require matching evidence; an unrelated validator cannot stand
in for one. This is an evidence API, not a validator-discovery/execution registry.

The scope gate requires `touched_files` and `scope_evidence_ref`. `None` means
missing inventory; `()` explicitly records an empty diff. Every path must match
`allowed_paths` and must not match `forbidden_paths` (forbidden wins). Paths use
the shared repository-relative, case-sensitive POSIX matching contract.
Absolute, escaping, ambiguous/control-character paths and concrete globs are
rejected. Policies must explicitly enumerate nonempty allowed scope; `('*',)`
is an explicit all-path specification. Policies do not implicitly inherit Auto
Dev's protected areas: callers should include the applicable protected-path
rules in `forbidden_paths` when forming the human-controlled task policy.

Optional `max_touched_files` and `max_changed_lines` are hard bounds.
`changed_lines` means additions plus deletions supplied by the collector; missing
counts cannot satisfy a configured bound. Binary changes still count as touched
files. Nonempty structured `violations` invalidate the candidate even if its
other checks succeeded. Empty required-test groups are rejected unless the
policy explicitly sets `allow_no_tests=True`; this does not waive core checks.

## Comparison and verdicts

Mandatory gates are evaluated first. Optimization evidence cannot rescue an
invalid candidate.

| Situation | Verdict |
| --- | --- |
| Only A passes all mandatory gates | `CANDIDATE_A_PREFERRED` |
| Only B passes all mandatory gates | `CANDIDATE_B_PREFERRED` |
| Neither passes all mandatory gates | `NO_VALID_CANDIDATE` |
| Both valid; A dominates every configured metric | `CANDIDATE_A_PREFERRED` |
| Both valid; B dominates every configured metric | `CANDIDATE_B_PREFERRED` |
| Both valid; tied, tradeoff, no metrics, or incomplete comparison | `EVIDENCE_INCONCLUSIVE` |

For each configured `MetricSpec(metric_id, unit, direction, context_id)`, both
candidates must supply a `Measurement` with exactly that identity, unit, and
protocol/context ID. `context_id` names the workload, version, environment,
sampling, and aggregation protocol agreed before candidate evaluation.
`direction` is policy-owned: `lower` for latency/memory or `higher` for
throughput/task score, for example. Arbitrary named **deterministically measured**
scalar metrics support coverage/complexity deltas or other task-specific scores;
there is no built-in scoring formula, model-confidence metric, or prose parser.

One candidate dominates only when no worse on every configured metric and
strictly better on at least one. Faster versus lower memory is a tradeoff and
remains inconclusive. All configured metrics are required **for comparison**;
missing or incompatible measurements make comparison inconclusive, not a
correctness-gate failure. Even an advantage on another metric cannot override
this. With one gate-valid candidate, the gates alone determine the preference.

No benchmarks are required by default (`metrics=()`). Measurements not named by
policy are excluded from comparison; they cannot create a tie breaker.
Required benchmark execution or performance-regression thresholds can be
expressed as required validator checks. Range/threshold checking, unit
conversion, noise analysis, and repeated-run aggregation belong to those
deterministic collectors/validators; no values or thresholds are invented here.

Measurements accept finite decimal strings, ints, or floats; floats are
converted using their Python decimal representation. Decimal strings are
recommended for exact evidence. Signed values allow deltas. NaN, infinity,
booleans, malformed numeric strings, and missing numeric values are rejected,
never defaulted to zero. Exact Decimal comparisons perform no arithmetic and
are independent of decimal precision/rounding context. No implicit epsilon or
rounding breaks a tie.

## Determinism, failure, and review

Records canonicalize collection order and reject duplicate IDs/paths. Required
core gates have a fixed order; other checks/metrics are sorted by ID; result
references are sorted and deduplicated. Set membership is used only for logical
decisions, never to pick a first candidate. No random number, clock, environment
probe, model call, provider name, confidence, command prose, or test duration
affects preference. The legacy adapter discards output summaries. Arbitrary
candidate explanations/context must be archived outside the authoritative API.

Malformed records and identity mismatches raise clear exceptions (validated
contracts use `ValueError`; invalid wire keys/shapes can also raise `TypeError`
or `KeyError`). Internal failures propagate; there is no heuristic or AI fallback.
Missing required gate evidence invalidates a candidate, while incompatible or
missing comparative evidence prevents dominance. A result includes the complete
policy, candidate artifact bindings, gate reasons and observed exit codes,
per-metric comparisons, evidence references, and `human_review_required=True`.
It conveys policy satisfaction, not independent approval or physical-safety
certification.

## Verification and synthetic integration example

The end-to-end unit test reconstructs JSON-shaped policy and evidence, evaluates
the public API, and serializes the result. Both candidates have clean mandatory
checks and 12 passed / 0 failed / 0 skipped required tests:

| A latency | B latency | Policy | Result |
| --- | --- | --- | --- |
| 102 ms | 117 ms | Same protocol, lower is better | `CANDIDATE_A_PREFERRED` |
| 117 ms | 102 ms | Same protocol, lower is better | `CANDIDATE_B_PREFERRED` |

All examples are synthetic observations; no model or candidate command is run.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_testcube_arbiter.py tests/test_autodev_protected_paths.py tests/test_autodev_packets.py tests/test_autodev_structure.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests -q
```

Independent Claude review should inspect the actual diff and these test results.
The implementer has not issued an independent approval. Live dual-candidate
generation, isolation, evidence collection, and promotion remain future work;
the arbiter is ready for synthetic or externally collected evidence trials.
