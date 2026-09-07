# TestCube trusted isolated collector

Candidate agents do not supply authoritative test, scope, benchmark, or safety
evidence. **AI proposes. Deterministic code disposes.**

The collector accepts two external Git diff artifacts, runs trusted commands
against a pinned base, and supplies the existing immutable `CandidateEvidence`
to the unchanged deterministic arbiter. It stops at a review artifact. There
is no model/provider integration, issue ingestion, promotion, merge, push, PR,
deployment, or scheduler.

## Architecture and supported host

`omni.testcube.collector.collect_and_evaluate` coordinates Git observations,
isolated execution, artifact publication, and receipt verification. It reuses:

- `backend.app.sandbox.execution.run_command`: the single subprocess boundary,
  argv-only, closed stdin, minimized environment, timeout/process-group kill,
  capture-time bounds for each output stream, and structured results.
- `ResourceLimits` and the existing standalone limit launcher: CPU, address
  space, file size, descriptors, and disabled core dumps.
- Auto Dev's repository-relative path normalization and scope matcher.
- The approved TestCube policy, evidence records, and `evaluate()` function.

Inspection found no existing worktree manager, patch collector, artifact hash
binding, or filesystem/network jail. The existing sandbox is explicitly not
a security sandbox; its process controls alone are insufficient here.

The added isolation boundary requires Linux user, mount, PID, IPC, UTS, and
network namespaces, `/usr/bin/bwrap` with `--json-status-fd` support, Git, and a
trusted Python virtualenv. Bubblewrap 0.6.1 is exercised on the development
host. Missing or denied isolation support produces `COLLECTION_FAILED`, with
no unrestricted fallback. No dependency is downloaded or installed by this code.

`isolated_runner.py` constructs fixed Bubblewrap mounts and composes them with
`run_command`; it is not a second subprocess implementation. Two small trusted
exec wrappers provide readiness and startup-failure observations through file
descriptors that candidate code never receives. Bubblewrap closes its status
descriptor in the sandbox child; its monitor owns completion reporting. See
[Bubblewrap's implementation](https://github.com/containers/bubblewrap/blob/v0.6.1/bubblewrap.c)
for that descriptor lifecycle.

## Isolation and immutable source

Each evaluation creates two independent local repository copies using
`git clone --no-local --no-hardlinks --no-checkout`. Copies have independent
object storage, Git metadata, indexes, and detached checkouts. Their origin
remotes are removed. The trusted source gets no worktree registrations, branch
changes, index writes, or candidate commits.

The collector resolves the trusted base specification once with
`git rev-parse --verify --end-of-options <base>^{commit}`. Both copies must have
that full commit, the expected root, a detached HEAD, and a clean initial
status. A setup mismatch is collector failure, not a failed candidate test.

Commands run inside these mounts:

| Path | Access |
| --- | --- |
| `/work` | Candidate checkout, read-only |
| `/work/.git` | Empty, read-only mask; real Git metadata unavailable |
| `/runtime` | Explicit trusted virtualenv, read-only |
| `/usr`, library/bin aliases | System tools and libraries, read-only |
| `/bootstrap.py` | Trusted collector exec bootstrap, read-only |
| `/tmp`, `/scratch` | Private tmpfs, fresh for every command |
| `/proc`, `/dev` | Namespace-local process view and minimal devices |

The trusted checkout, peer candidate, artifact directory, user home,
credentials, host sockets, and policy source are not mounted. Network and PID
namespaces are separate, capabilities are dropped, and processes die with the
wrapper. Read-only source also prevents a build or test from rewriting the
patch or validation files between checks. Git operations against `/work`
cannot mutate any repository; private scratch operations confer no authority
over trusted Git state or remotes.

Commands must place outputs in `/scratch` or `/tmp`. Scratch is not shared
between commands: configure a single trusted command when compilation and use
of its output must happen together. Builds requiring writable source, writable
Git metadata, network dependency installation, or persistent scratch are not
supported in this initial collector. The base must not contain symlinks or
submodules; a patch introducing either fails safety before execution. This is
a deliberate initial restriction, not a claim to support arbitrary repositories.

The host kernel, system tools, collector code, runtime, and operator are trusted.
This is namespace/mount isolation, not a VM or protection against kernel
exploits. Existing limits provide no aggregate disk/memory cgroup quota or
process-count limit. Do not interpret passing tests as certification against
every denial-of-service attack.

## Trusted configuration and patch input

`CollectorPolicy` contains the existing `CandidatePolicy`, trusted base
specification, canonical virtualenv path, exact `CommandSpec` argv/limits, and
optional `BenchmarkSpec` protocols. Commands may implement only required
`build`, `test:<group>`, `validator:<name>`, and `static:<name>` checks. Callers
cannot override collector-owned apply/diff/safety/operation gates. A missing
required command leaves missing evidence; it never becomes success.

There is no natural-language command selection or shell-string execution.
Argv executables must be in the trusted system/runtime bin directories.
Arguments and test entry points are operator-owned configuration. The operator
must protect the actual validation suite and relevant test configuration with
allowed/forbidden path policy; namespace isolation does not prove a task's
tests are sufficient or prevent all forms of application-level test evasion.

Untrusted input is limited to patch bytes and the candidate code they produce.
The collector reads a bounded regular file without following a terminal symlink
or blocking on a FIFO, retains its bytes, computes SHA-256 and byte size, and
publishes an exclusive `patch.diff`. It applies that snapshot, never reopens a
mutable original filename. Supported input is Git-generated unified diff
(`diff --git ...`), including Git binary patches. Empty, NUL-containing, other
formats, or non-applicable patches fail application without heuristic repair.
Unreadable/oversized artifacts prevent trustworthy collection and fail the run.

`patch_ref` contains evaluation ID, full base commit, and collector-computed
patch digest. The candidate slot is bound by `EvidenceIdentity` on every record.
Distinct patch bytes have distinct refs; identical bytes in the same evaluation
truthfully share a digest/ref while keeping separate A/B identities.

## Observations and gates

The collector applies with `git apply --index --binary --whitespace=nowarn` in
the disposable copy, records the actual result, and runs
`git diff --cached --check <base>`. Staged diff is intentional: the index names
the exact applied candidate, including additions. No whitespace is repaired.

Changed paths come from NUL-delimited Git name/status records with rename/copy
detection. Both sides of renames/copies are included, as are additions,
deletions, modifications, and type changes. Lossy/unrepresentable filenames
fail collection. Scope and size are independently checked before commands run.

Line counts use NUL-delimited `--numstat --no-renames`: additions plus deletions;
a rename therefore counts deletion/addition content under this explicit scope
protocol. Binary paths are recorded and make `changed_lines=None`. A configured
line limit cannot pass with that missing count. No binary change is silently
counted as zero.

Each command record stores requested argv, `/work` cwd, actual exit code,
duration, bounded stdout/stderr refs, timeout/output/resource classifications,
and isolation handshake artifacts. Zero exit is authoritative. Timeouts retain
`outcome="timeout"`; output overflow has `outcome="error"`; neither can pass.
Setup/exec/runner uncertainty is infrastructure failure. Test counts remain
`None`: parsing candidate-process output or a candidate-writable report would
not establish trusted counts. Printed assertions such as “12 passed” are never
converted to a result.

The safety gate combines scope/size checks with the initial mode restrictions.
The operations gate records enforced mount/namespace restrictions and unchanged
candidate index/tree/metadata observations. It is not a shell-history parser
or a claim to recognize every command attempted inside private scratch.

The trusted source's HEAD, refs, status, and hashes of index/config metadata are
compared before/after. Config/remotes are hashed, not archived in plaintext.
The integration tests additionally compare every byte in their small source
repositories, including Git metadata. Any observed integrity mismatch aborts
arbitration without attempting repair or reset.

## Optional benchmarks

Initial support is collector-measured elapsed time in `ms`, lower is better.
The trusted policy supplies the metric ID, unit, direction, context ID, exact
workload command, limits, and odd sample count (1/3/5/7/9). A and B use the same
protocol, in alternating A/B order per sample, with fresh scratch. The median
comes from the parent's monotonic nanosecond measurements, including isolation
startup overhead. Raw samples and command outputs are retained.

The collector never parses benchmark stdout as a number. Failed or incomplete
samples yield no `Measurement`; no value defaults to zero. Metrics without a
configured collector protocol remain absent. The arbiter performs all comparison.
Timing naturally varies, and this protocol does not claim noise-free performance
measurement. Workload adequacy and tolerances remain trusted policy concerns.

## Artifacts, authenticity, and lifecycle

The caller supplies an existing operator-owned output root disjoint from the
source and exposed runtime mounts. Each evaluation ID is single-use:

```text
<output-root>/<evaluation-id>/
  policy.json, environment.json, source-integrity.json
  git/command-NNNN.json
  candidate-A/                         # same layout for B
    patch.diff, patch.sha256
    changed-paths.json, safety.json, operations.json
    checks/<check-id>.{json,stdout.txt,stderr.txt,launch.json,status.jsonl,...}
    benchmarks/<metric-id>/sample-NN.*, summary.json
    evidence.json
  manifest.json, arbitration-result.json
  worktrees/A/, worktrees/B/           # retained by default
  cleanup.json                         # only after explicit cleanup
```

Artifacts are exclusively created and fsynced. The manifest binds the full
base, policy hash, patch hashes/sizes, artifact digests, and human-review status.
Environment metadata records Python/platform, Git/Bubblewrap versions, runtime
interpreter digest, collector code revision and file digests, without dumping
the environment. Durations and namespace/process IDs are audit metadata; they
do not influence arbitration except explicit elapsed-time measurements.

`CollectionReceipt` holds the manifest digest and expected identities outside
the bundle. `arbitrate_collected(receipt, policy)` verifies the manifest, policy,
all listed artifact hashes, patch bytes, and reconstructed candidate identities
before calling `evaluate()`. Changing a patch, evidence identity, base, or policy
is detected against that retained receipt. The archived arbitration result is
derived output; re-verification reconstructs it instead of trusting that file.

SHA-256 binding is not a digital signature. The receipt and policy must stay
trusted: someone able to replace the bundle **and** the trusted receipt can
forge a new bundle. Candidate processes can access neither. Concurrent hostile
host processes or an operator replacing trusted toolchains are outside this
boundary.

Outcomes are `EVIDENCE_COMPLETE` (both candidates pass gates),
`CANDIDATE_INVALID` (reliable evidence, at least one gate-invalid candidate), and
`COLLECTION_FAILED` (infrastructure/integrity failure; no arbiter result returned).
Benchmark absence can leave complete gate evidence but an inconclusive verdict.
Failures retain partial artifacts and an error record where writing is possible.

Copies remain by default. `cleanup=True` or `cleanup_collection(receipt, policy)`
verifies durable evidence first and removes only the collector-owned
`worktrees/` directory using symlink-safe removal. Evidence survives cleanup;
cleanup failure is reported and never claimed as complete success.

## API and verification

Import the collector explicitly; `omni.testcube` continues to expose only the
pure arbiter surface:

```python
from omni.testcube.collector import collect_and_evaluate, arbitrate_collected

collection = collect_and_evaluate(
    source_repo=source, patch_a=patch_a, patch_b=patch_b,
    policy=collector_policy, output_root=evidence_root,
)
if collection.receipt is not None and collection.arbitration is not None:
    result = arbitrate_collected(collection.receipt, collector_policy)
    # result.winning_artifact_ref is for human review only.
```

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_testcube_collector.py tests/test_testcube_arbiter.py tests/test_autodev_packets.py tests/test_autodev_protected_paths.py tests/test_sandbox_execution.py tests/test_sandbox_resource_policy.py tests/test_sandbox_limited_launcher.py tests/test_sandbox_command_report.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests -q
```

Real disposable-repository tests exercise the incorrect subtraction function,
A's addition fix, B's incorrect multiplication patch, and the reversed scenario.
Other regressions cover isolation, actual command failure/timeouts, complete
path inventory, hash/identity tampering, benchmark failures, and cleanup.
Namespace-requiring tests fail explicitly when the host cannot provide the
required isolation; they are not skipped or replaced with unrestricted execution.

This milestone requires independent review before live model-produced patches.
It supplies no live candidate generation or autonomous promotion authority.
