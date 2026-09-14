# OMNI Super-Build Box v0

This implementation checkpoint adds persistent, isolated project development.
An accepted result advances a project-local detached Git commit. Trusted OMNI
is only a read source during creation and has no application/promotion endpoint.
Independent review is required before any real Super-Build.

## Responsibility boundaries

| Component | Responsibility | Authority it does not have |
| --- | --- | --- |
| TestCube v1 | Structured-edit rendering, isolated candidate competition, trusted evidence, deterministic arbitration | Accept a project checkpoint |
| Super-Build Box v0 | Persistent project identity, bounded work, audit history, verified project-local acceptance | Run providers, select the next task, promote into OMNI |
| Future scheduler | Decide when/which separately authorized work item to run | Change validators, forge human decisions, promote |
| Future promotion system | Separately reviewed human-controlled export/promotion pathway | No implementation exists here |

There is no scheduled autonomy, issue ingestion, task creation, retry loop,
provider call, PR creation, push, deployment, or Simulation Core implementation.
The production CLI is `python -m omni.superbuild`. No dependency was added.

The new package boundary is justified by a new state owner: TestCube operates
on one immutable base per competition; Super-Build owns an accumulating chain
of accepted bases. TestCube's existing modules and behavior are unchanged.
The box imports its strict task/policy models, canonical JSON/SHA-256 helpers,
collector, receipt verifier, and scope inspection helpers. Its Git wrapper
uses the same bounded subprocess wall and hardening, without writing audit
files during read-only verification. Its additional raw-byte checkout checks
protect persistent state against stale Git stat caches.

## Identity, workspace and persistent state

`SuperBuildProject`, `SuperBuildState`, `SuperBuildWorkItem`,
`SuperBuildCheckpoint`, and `SuperBuildDecision` are frozen validated dataclasses.
Unknown fields/versions, malformed hashes, identities, decisions, and parent
bindings fail closed. Project/work IDs are operator-owned, restricted ASCII,
single-use names. No model-output decoder accepts them as authority.

The default private root is `~/omni_superbuild`. Tests use `/tmp`. Storage must
be outside both the trusted source and the running OMNI installation, without
symlink aliases. The root must be owned by the operator with no group/other
permission bits. Source creation requires a clean tracked/untracked checkout at
the exact full SHA-1 origin commit; ignored source runtime files are not copied.

Each workspace is `git clone --no-local --no-hardlinks --no-checkout --template=`
followed by detached checkout. There is no shared object database, worktree
registration, alternate object path, remote, or branch. Only clone-local refs
are removed. All post-creation Git writes target the project workspace.
The original commit remains an ancestor of every accepted commit.

```text
<private root>/
  locks/<project ID>             permanent flock inode
  registry/<project ID>.json     operator-owned project/history anchor
  <project ID>/
    project.json                immutable origin, policy and workspace descriptor
    manifest.json               replaceable index, replayed state, record hashes
    records/00000000.json ...    exclusive, hash-linked append-only events
    evidence/<work item>/       complete retained TestCube receipt bundle
    inputs/<work item>/         hashed input snapshots, accepted commit message
    workspace/                  independent detached Git repository
    transaction.json            present only during a mutation or after a crash
```

The initial accepted commit equals `trusted_source_commit` (also exposed as
`origin_commit`). Its checkpoint identity is the immutable project descriptor's
SHA-256. Subsequent checkpoint identities hash the canonical checkpoint record.
The manifest explicitly names `origin_commit`, `accepted_project_commit`,
`accepted_checkpoint`, all work items, decisions, and checkpoints in `state`.
The accepted pointer is never resolved from trusted OMNI's current HEAD.

Each event binds its sequence and preceding event digest; the first binds the
project descriptor. Decisions and checkpoints are never rewritten. The
registry pins the descriptor hash, current manifest hash, history count and tip
outside the per-project directory. The summary must exactly equal a fresh
replay of the anchored records. Copying back an older project directory without
its registry anchor, modifying only a manifest, deleting a record, or modifying
an artifact fails verification. A lost summary can be reconstructed from the
records during offline human repair; normal startup never silently repairs it.

These hashes are not digital signatures. The operator, host, registry, Python
control plane, trusted validation configuration, Git and kernel are trusted.
An attacker with arbitrary operator-level filesystem/Python access can rewrite
both history and its external anchor or spoof a terminal. This is not a defense
against that attacker, a filesystem backup system, or a kernel security boundary.
Backups must include the entire root, including registry, Git objects, evidence,
and history. No timestamps or log ordering are used to guess missing state.

## Bounded work and all lifecycle transitions

A work item carries the project/work ID, parent checkpoint and full accepted
commit, a `CandidateTaskSpec`, its matching `CollectorPolicy`, and status. The
task binds the task specification, allowed/forbidden paths, required tests and
validators, protected validation paths, and size limits. The policy binds exact
validation argv and limits. A new task must use the current accepted state;
stale definitions are rejected, never silently rebased. One nonterminal item
per project is allowed, including `PENDING`. Completed IDs cannot be reused.

| From | Allowed next states | Owner |
| --- | --- | --- |
| PENDING | READY, ABORTED | Operator |
| READY | GENERATING, ABORTED | Operator |
| GENERATING | EVALUATING, GENERATION_FAILED, ABORTED | Trusted evaluation entry point, or operator failure/abort |
| EVALUATING | AWAITING_HUMAN_DECISION, EVIDENCE_FAILED, ABORTED | Trusted evidence handler, or operator failure/abort |
| AWAITING_HUMAN_DECISION | ACCEPTED, REJECTED, ABORTED | Human decision, or operator abort |
| ACCEPTED, REJECTED, ABORTED, GENERATION_FAILED, EVIDENCE_FAILED | None | Terminal |

`DEFER` appends a human decision and leaves `AWAITING_HUMAN_DECISION` unchanged;
it is not a state transition. There are no retries or terminal-to-ready edges.
Interrupted evaluation is blocked by the transaction marker; it does not become
an operator-abortable clean state until offline inspection resolves the crash.

`GENERATING` is a durable lifecycle label here. The operator supplies synthetic
rendered patches; no Claude/Codex launcher is connected. `evaluate()` owns input
snapshotting and calls the existing TestCube collector. The collector's exact
receipt, candidate evidence digests, and arbiter verdict are appended to history.
Every reload rechecks that receipt and its artifacts with `arbitrate_collected`.
Failed collection records `EVIDENCE_FAILED` and retains hashed input snapshots;
any collector failure diagnostics have no acceptance authority.

## Human acceptance and application

Only `decide()` can create the authoritative decision/checkpoint sequence.
It accepts operator-selected IDs, parent, exact evidence digest and, for an
acceptance, exact candidate-evidence and patch digests. `ACCEPT_A`/`ACCEPT_B`
select a slot; `REJECT_BOTH` and `DEFER` cannot select artifact hashes.
Deserializing a `SuperBuildDecision` only reconstructs an audit record: there
is no endpoint to submit a model-created record as an authorized decision.

Before prompting, the machinery validates all bindings, actual collector
evidence, allowed scope, existing-file modifications, and the selected slot's
mandatory gates. A human may choose either gate-valid candidate, regardless of
arbiter preference; a human cannot waive failed mandatory gates through this API.
Even `CANDIDATE_A_PREFERRED` only reaches `AWAITING_HUMAN_DECISION`.

The full proposed decision is displayed on `/dev/tty`. The operator must type
the exact decision, project/work identity and canonical decision digest.
Piped stdin, a supplied `authority="model"`, or model JSON cannot confirm it.
There is no `--yes`, environment switch, injectable approval callback, or live
provider channel. Tests monkeypatch the private terminal reader to simulate
operator actions; production never provides a synthetic approval mode.
The operator name is an audit attribution, not an identity-authentication service.

After confirmation all durable evidence and workspace integrity are checked
again. A durable transaction marker and immutable decision event precede any
application. Trusted Git checks and applies the exact hashed patch with an
index. Scope and whitespace are independently checked on the staged diff;
the staged tree must exactly match TestCube's recorded evaluated `index_tree`.
Only then is a project-local commit created, with the full decision in its
message: project/work ID, slot, candidate digest, patch digest, evidence digest,
parent checkpoint/commit, operator and time. The checkpoint also binds the
decision digest. Reload checks exact one-parent ancestry, commit message, and
evaluated tree identity for every accepted checkpoint.

Git hooks, external diff/textconv, global/system config, automatic maintenance,
signing, remote access and object replacement are disabled in the relevant
operations. Workspace config is hashed at creation and checked before Git
reads it on resume. Symlinks, submodules, alternate objects, grafts, replacement
refs, sparse/assume-unchanged index flags and noncanonical paths fail closed.
Candidate code executes only inside unchanged TestCube isolation, with a
read-only evaluation copy and masked Git metadata. It cannot reach the accepted
workspace, registry, source, or peer copy through the configured mounts.

## Restart, locking and interrupted mutations

`verify_superbuild_project(root, project_id)` reconstructs all state from disk
and returns `SuperBuildState`, or raises an integrity exception. It verifies
canonical manifest/descriptor/registry bindings, record hashes and sequence,
every transition, origin and accepted commits, detached HEAD, absence of
untracked/ignored changes, actual file bytes/modes against Git blobs, checkpoint
ancestry and trees, decisions, input snapshots and retained evidence hashes.
Verification never checks out, repairs or commits anything.

All reads/mutations acquire the same nonblocking POSIX `flock`. A second process
gets `ProjectBusy`; a lock is released by the OS on process death. Its inode is
never unlinked. There is no distributed or parallel work-item scheduling.
Resume works after an ordinary restart in any clean lifecycle state. It requires
the same canonical storage path; relocation is an offline future operation.
The original source repository need not be available after creation.

Records and temporary manifests use exclusive creation and file/directory
`fsync`. Replaceable manifests and registry anchors use atomic rename with
directory synchronization. Project checkout/Git data and successful collection
bundles are flushed before pointer publication. A transaction marker spans
all multi-file changes and is removed only after successful publication.

| Interruption | Startup behavior |
| --- | --- |
| Before candidate application | `RecoveryRequired`; decision and intent retained |
| During application (including partial worktree writes) | `RecoveryRequired`; no accepted-state guess |
| After patch, before commit | `RecoveryRequired`; staged/dirty workspace preserved |
| After commit, before manifest update | `RecoveryRequired`; new Git commit does not authorize a guessed pointer |
| After manifest/registry update, before marker removal | `RecoveryRequired`; publication alone does not erase unresolved intent |
| After successful marker removal and sync | Verify and reconstruct normally |

This checkpoint deliberately uses the permitted **fail-closed requiring human
intervention** recovery policy. There is no automatic rollback, reset, forward
completion, retry, or marker-removal command. After `RecoveryRequired`, preserve
the entire root, stop writers, and inspect the intent, immutable records,
registry, evaluated trees and Git state. Any repair must be separately scoped
and reviewed; deleting the marker is not a supported recovery procedure. Tests
use child-process `os._exit` at all five boundaries so Python cleanup cannot
make the interruption look successful.

## Operator entry points and evidence

```bash
python -m omni.superbuild --root /private/omni_superbuild create \
  --project-id SUPERBUILD-001 --title 'Example project' \
  --description 'Human-scoped project' --source-repo /clean/trusted/source \
  --origin-commit 5fe6db20df83e1945c1163288201ab16ba2109ca
python -m omni.superbuild --root /private/omni_superbuild verify SUPERBUILD-001
python -m omni.superbuild --root /private/omni_superbuild add-work --file /operator/work.json
python -m omni.superbuild --root /private/omni_superbuild advance SUPERBUILD-001 WORK-001 READY
python -m omni.superbuild --root /private/omni_superbuild advance SUPERBUILD-001 WORK-001 GENERATING
python -m omni.superbuild --root /private/omni_superbuild evaluate SUPERBUILD-001 WORK-001 \
  --patch-a /operator/A.diff --patch-b /operator/B.diff
```

`decide --help` lists the required identity/digest arguments. The evidence event
in `records/` carries `receipt.manifest_sha256`, ordered A/B `candidate_digests`
and `receipt.patch_sha256`; `verify` reports the current parent commit/checkpoint.
Inspect the retained bundle before deciding. The work JSON shape is
`asdict(SuperBuildWorkItem(...))`; the tests show concrete operator-owned task and
policy construction, including protected validators and exact argv.

The synthetic tests use real disposable Git repositories, trusted rendering,
real isolated TestCube validation, synthetic terminal input, and zero providers.
`test_superbuild_demo.py` starts at the exact `testcube-v1` commit in a clean
disposable clone and adds two harmless comments to `memory/memory_manager.py`.
Its second validator explicitly requires the first accepted comment. Each step
verifies the trusted source's HEAD, refs, index/config and status are unchanged,
as well as preservation of the real tag. `demonstration.json` in the pytest
temporary directory records both project-local commits and decisions.

| Property | Test evidence |
| --- | --- |
| Creation, immutable origin, isolated storage, initial state, reload | `test_creation_origin_reload_isolation`, overlap tests |
| Bounded work and transitions | `test_work_creation_parent_and_one_active`, durable failure/terminal lifecycle tests |
| Human authority and A/B/reject/defer | decision schema, model rejection, no-terminal and decision tests |
| Hash, parent, patch and decision bindings | wrong-binding, durable tampering, human-pause tampering tests |
| Project-local apply/commit and cumulative work | two-step fresh-process test and exact-tag demonstration |
| Workspace and history integrity | workspace tamper, semantic history, ancestry/evaluated-tree tests |
| Restart/concurrency/interruption | process reload, cross-process lock, five abrupt-exit tests |
| Existing TestCube behavior | unchanged structured-edit, harness, collector, arbiter, provider and sandbox suites |

## Limits and future use

The persistent-state architecture can support a future multi-step Simulation
Core build. Its current execution policy intentionally retains TestCube v1's
small-bugfix bounds: existing regular Python files, at most three files/100
changed lines, no new-file/module creation, no benchmarks or high-risk work.
The Super-Build control plane itself is also excluded from candidate scope.
Expanding that policy and connecting read-only providers require separate
implementation and independent review. The present implementation does not yet
support performing a substantial new subsystem build.

Within the configured boundaries: providers cannot mutate trusted OMNI or the
accepted project; the arbiter cannot accept; acceptance requires a terminal
decision; mismatched evidence/hash/parent cannot apply; later work cannot ignore
the accepted parent; durable work survives restart; trusted OMNI can remain
frozen while the project evolves. Providers are absent in v0, and future mounts
must preserve TestCube isolation rather than exposing the accepted workspace.
Promotion remains a separate future human-controlled pathway with no runtime
implementation here. Passing tests are implementation evidence, not independent
approval or safety certification.

## Observed implementation validation

Starting branch: `omni/superbuild-box-v0`. Starting HEAD:
`5fe6db20df83e1945c1163288201ab16ba2109ca`, with a clean worktree and exact
`testcube-v1` tag. The annotated tag object is
`f2f302d168c001307cf033c8cc187039ae21b318`; its peeled commit remains the starting
HEAD. No historical commit or TestCube source/test file was changed.

The standalone pinned demonstration passed (`1 passed in 74.11s`). Its observed
project-local commit chain was:

```text
5fe6db20df83e1945c1163288201ab16ba2109ca
  -> 9425ba426684fd58266ef2341b79271086195ca5
  -> 5d4dab2afe8d7a88c895f609a890a5f81901bb78
```

Both persisted decisions were synthetic `ACCEPT_A`; reload/integrity, cumulative
state, source immutability and tag preservation passed. These are disposable
fixture commits, not OMNI commits or promotion approvals.

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_superbuild.py tests/test_superbuild_demo.py -q
61 passed in 151.81s (0:02:31)

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_superbuild.py -q -k 'storage_names or creation_origin'
3 passed, 59 deselected in 0.76s

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_testcube_edit_transport.py tests/test_testcube_candidate_harness.py tests/test_testcube_collector.py tests/test_testcube_arbiter.py tests/test_frontier_claude_provider.py tests/test_frontier_codex_provider.py tests/test_sandbox*.py -q
839 passed in 124.37s (0:02:04)

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests -q
3450 passed, 2 warnings in 318.28s (0:05:18)
```

The focused run includes two reserved-ID regressions added after collection of
the 61-test run, plus the existing creation test. The initial restricted run
failed with Bubblewrap's `Operation not permitted` namespace setup error;
subsequent integration runs used execution permission outside the outer Codex
sandbox, retaining TestCube's real isolation boundary. Real Claude calls: **0**.
Real Codex calls: **0**. Independent review remains outstanding.
The full suite includes all 63 final Super-Build tests. Its two existing warnings
concern Google's Python 3.10 support and deprecated `google.generativeai` package.
No dependency or unrelated warning cleanup belongs to this checkpoint.
