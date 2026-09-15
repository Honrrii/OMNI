# Supervised TestCube candidate generation

**AI proposes. Deterministic code disposes.**

This milestone connects two independent patch proposals to the approved
collector and deterministic arbiter. It does not run a research debate, select
an issue, schedule work, or promote a patch. Provider identity is provenance,
not an arbitration signal. A TestCube winner is a candidate for human review,
not permission to modify trusted OMNI.

## Trust boundary and reuse

The human supplies a frozen `CandidateTaskSpec`, a `CollectorPolicy`, provider
configuration, a clean trusted repository, and an existing external output
root. Models supply one strict structured-edit JSON result each. Trusted code
validates exact replacements against the pinned base and Git renders the patch
that enters the collector. Summary, assumptions, limitations, confidence-like
prose and recommendations cannot become `CandidateEvidence` or choose a winner.

`candidate_providers.py` reuses the existing Frontier Claude/Codex configuration,
availability/authentication functions, `PreflightResult`, and read-only argv
builders. Patch output has different semantics from `FrontierMessage`, so no
research adapter, mailbox, orchestrator, role skill, debate history, or state
machine is used. The dual-preflight conjunction is composed locally rather
than importing the Frontier CLI into the library.

Frontier's original process runners buffer output until exit. This harness
instead reuses `backend.app.sandbox.execution.run_command` for capture-time
output bounds, timeout enforcement, closed inherited descriptors and process
group termination. `provider_bootstrap.py` only opens the trusted prompt as
stdin and execs the fixed argv. There is no second subprocess implementation,
shell interpolation, heuristic repair, reassessment or automatic retry.

The collector, arbiter, Frontier providers, and historical
`OMNI-FRONTIER-0001` are unchanged by this phase.

## Task ownership and eligibility

The initial supported operation is deliberately narrow: a human-classified
`small_bugfix`, affecting 1–3 explicitly named existing Python files, at most
3 touched files and 100 changed lines, with a patch cap of 128 KiB. No globs
or directory-wide allowed scope are accepted. Protected Auto Dev paths and
explicit first-trial security, safety, auth, schema, migration, deployment,
test, provider and harness paths are excluded.

`risk_categories` must be empty. Any declared benchmark comparison,
safety-policy redesign, credential/auth change, CI-secret change, deployment,
dependency upgrade, large refactor, schema migration or destructive data
change is rejected. This is an explicit human classification contract and
path guard, not a natural-language intent classifier. Misclassifying a task
is outside the trusted-input boundary; humans must review eligibility.

Required test/validator IDs, allowed/forbidden paths, base and size limits must
agree exactly with the supplied collector policy. Every required command must
exist before generation. `validation_paths` names the existing tests and
relevant test configuration the operator is protecting; those files must be
explicitly forbidden to patches. Operators remain responsible for validation
adequacy and application-level test evasion, as documented by the collector.

`CandidatePolicy.metrics` and collector benchmarks **must both be empty**.
This guard cannot be disabled by a CLI flag. The reviewed collector currently
runs A before B in each benchmark sample; this phase does not change it.
Correctness gates determine eligibility for the first trial. If both candidates
pass without comparative metrics, `EVIDENCE_INCONCLUSIVE` is expected.

## One base, independent read-only providers

The harness resolves the requested revision to a full immutable commit before
preflight. The trusted checkout must be clean and its HEAD must equal that
commit, so live file inspection and later evaluation see the same source.
Assume-unchanged/skip-worktree index flags are rejected; declared source and
validation paths must be tracked, so a misleading clean status or ignored
local file cannot silently substitute for the pinned source.
For an older base, the operator must prepare a separate trusted checkout;
the harness does not switch the trusted branch. Collector-unsupported base
symlinks/submodules and invalid runtime paths are rejected before generation.

Claude always occupies A; Codex always occupies B. Both receive the same task
and resolved base, plus their own slot. Neither prompt contains peer output,
and neither provider chooses its identity, policy, tests or base. Before and
after provider calls, repository observations must still match the initial
trusted snapshot. The collector independently enforces its own base and
integrity checks.

Claude's existing argv boundary is narrowed to `Read,Grep,Glob` only. Bash,
Edit, Write and NotebookEdit are unavailable. Restricted/safe mode, strict MCP
configuration, noninteractive permission denial and no session persistence
disable custom tool authority and keep file inspection within working roots.

Codex retains explicit `--sandbox read-only`, with no approval escalation,
ephemeral sessions, ignored user config/rules, and disabled multi-agent,
apps and hooks features. Local `.codex/config.toml` files along the repository
ancestry are masked with empty regular files inside the provider namespace;
an empty MCP override alone is insufficient because configuration can merge.
Managed host policy is trusted and is not bypassed. Codex emits its final
JSON response through bounded stdout; it receives no writable output-artifact
path. These stdout/ephemeral/config flags are described in the
[official noninteractive Codex documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
and were checked against the installed CLI help during implementation.

Both provider processes also run inside a Bubblewrap namespace: host files
and the repository are read-only; `/tmp`, `/run` and the process view are
private; the external trial output root is masked. This protects OMNI even
from CLI bookkeeping or tool subprocess writes and prevents cross-candidate
artifact reads. No provider session files are persisted. Candidate A cannot
leave a file in private scratch for B.

Generation requires network access for the authenticated provider CLI, so its
namespace shares networking. This is distinct from collector execution, which
still unshares networking and excludes host credentials. The provider CLI,
host kernel, managed policy, runtime and operator are trusted. This is not a
VM, a denial-of-service certification, or an isolation boundary against a
hostile operator replacing trusted tools. Authentication is read by the CLI;
the harness does not read/copy credential files, archive auth output, archive
stderr, or dump the environment. Auth requiring refresh or CLI state writes
outside private scratch must be prepared by the operator outside the trial;
there is no writable fallback. No live compatibility trial is claimed here.

## Output and call budgets

Each provider must return exactly this shape, with no extra/duplicate keys:

```json
{
  "schema_version": "omni.testcube.candidate-edit.v1",
  "summary": "Non-authoritative explanation",
  "edits": [{"path": "calc.py", "before": "a - b", "after": "a + b"}],
  "assumptions": [],
  "limitations": []
}
```

Claude's CLI success envelope must contain this object as `structured_output`;
Codex's final stdout must be this object directly. Invalid JSON, duplicate
keys, nonfinite JSON (including exponent overflow), incorrect types, extra
control fields, empty before strings, NUL bytes, oversize output, ambiguous
matches and overlapping source ranges fail generation. No prose scraping,
omitted-field inference or output repair is performed.

The default library and supervised CLI transport is explicitly versioned
`omni.testcube.candidate-edit.v1`. A human library caller may explicitly select
`candidate_transport="omni.testcube.candidate.v1"` for legacy compatibility;
the fake CLI exposes the same choice with `--candidate-transport`. The live CLI
selects only the new version. Every invocation gets exactly one schema and
validator, never an ambiguous either-format parser. Existing legacy fake and
native CLI fixture tests explicitly select their old transport.

The [structured transport contract](testcube_structured_edit_transport.md)
details the trusted renderer. It supports existing UTF-8, LF-only regular
Python files without BOM or Git attributes on edited paths. It bounds proposals
(including the raw success envelope) and canonical audit JSON to 128 KiB,
16 edits, 16 KiB per before/after, and 64 KiB total per side. Source files are
bounded to 1 MiB. The rendered patch still obeys `max_patch_bytes` and the
human-owned file/line limits. All replacements resolve against original base
bytes. Git computes headers, blob hashes and hunk counts in disposable copies;
a fresh copy must accept `git apply --index --binary` and reproduce the exact
expected bytes and modes. A trusted rendering inconsistency is classified
`RENDERER_FAILURE`, never provider `INVALID_OUTPUT`. The trial remains
`GENERATION_FAILED` and collection is not reached. The collector independently
derives scope, applicability and correctness afterward.

Both providers must pass authentication/version preflight before either
generation call starts (`DUAL_READY`). Truncated, oversized, malformed or
uncertain preflight output fails closed. Default budgets are one CLI generation
invocation per provider, 180 seconds each, 400,000 bytes per captured stream,
and zero harness retries. Configuration may lower these limits, or increase
timeout/output within enforced ceilings of 600 seconds/2 MiB. One CLI
invocation may internally perform multiple model/tool requests while inspecting
files; this is not a promise of one billable API request. The wall-clock and
output limits bound that single invocation; there are no harness debate rounds
or agent loops.

## Durable handoff and outcomes

The output root must be outside both the trusted repository and exposed
collector runtime. Each task/trial ID is single-use:

```text
<external-output-root>/<task-id>/
  task.json, base.json, requested-policy.json, collector-policy.json
  providers.json, source-integrity.json
  git/command-NNNN.json
  generation/candidate-A/                 # same for B
    prompt.txt, raw-output.json, proposal.json, patch.diff, generation.json
  collection/<task-id>/                   # unchanged collector layout
  manifest.json
```

Files are exclusively created, fsynced, and bound into the trial manifest.
Generation records include provider/version, trusted slot, task digest, base,
argv, prompt digest, call number/start/duration/exit classification, transport
version, and proposal/patch SHA-256/size. Proposal edits are canonically ordered
independently of provider array ordering; the retained raw stdout preserves the
original response. Raw stdout is bounded audit data, including malformed
responses; it is never interpreted as evidence. Authentication preflight
payloads and stderr are not saved. The known raw-output limitation remains:
a model can deliberately
echo readable credentials into generation stdout. Structured transport is not
a secret scrubber. The new code does not read credential files, serialize the
environment, or copy provider stderr; accepted model text remains untrusted
audit context and proposed code.

The harness checks proposal and rendered patch digests immediately before
handoff, then checks the collector receipt's hashes and base against generation records,
and checks the published patches again. A change between publication and
collector snapshot fails the trial; no mismatched recommendation is returned.
Only the collector creates `CandidateEvidence`; only the arbiter determines
preference.

The final manifest binds task, base, provider calls, generation records,
artifact digests, collector receipt/outcome and arbiter result, with
`human_review_required=true`. Retain the returned `TrialReceipt` outside the
bundle. `verify_trial(receipt, original_collector_policy)` verifies the manifest
and generation artifacts, delegates collector verification, and reconstructs
the verdict. Hash receipts are not signatures: replacing both a bundle and
its trusted receipt is outside their authenticity guarantee.

| Trial outcome | Meaning |
| --- | --- |
| `GENERATION_FAILED` | Invalid task/setup, failed dual preflight, provider failure, invalid output, generation tampering or trusted source integrity failure; no fabricated opponent/evidence. |
| `COLLECTION_FAILED` | Collector infrastructure, handoff identity, or durable trial publication/verification failure; no recommendation returned. |
| `TRIAL_COMPLETE` | Both patches collected with trustworthy evidence and an arbiter verdict. Does not imply a winner or approval. |

Underlying collector states remain available. A complete trial can yield any
of `CANDIDATE_A_PREFERRED`, `CANDIDATE_B_PREFERRED`, `NO_VALID_CANDIDATE`, or
`EVIDENCE_INCONCLUSIVE`. Partial failures preserve available audit artifacts;
publication errors are reported, never silently treated as success. Copies and
evidence remain for review; the harness does not add cleanup/promotion authority.

## Operator interface

`python scripts/omni_testcube.py --help` lists three explicit commands. No
default command launches a provider. Use a human-owned task JSON with the
fields from `CandidateTaskSpec`, and a separate JSON array of trusted
`CommandSpec` objects (`check_id`, `argv`, optional timeout/output limits).

```bash
python scripts/omni_testcube.py validate-task \
  --task /path/to/task.json --commands /path/to/commands.json

python scripts/omni_testcube.py fake-dual-candidate \
  --task /path/to/task.json --commands /path/to/commands.json \
  --repo /path/to/clean/repository --output-root /external/trials \
  --claude-output /path/to/fake-claude-envelope.json \
  --codex-output /path/to/fake-codex-candidate.json
```

The fake pathway still runs the real collector and real isolated commands.
It replaces only provider processes with inert file responses.

After independent review and a separate human instruction to perform the
billed trial, the explicit live command is:

```bash
python scripts/omni_testcube.py supervised-dual-candidate-live \
  --task /path/to/task.json --commands /path/to/commands.json \
  --repo /path/to/clean/repository --output-root /external/trials
```

It prints the real-provider/read-only/isolation/no-merge/human-review banner
before preflight. Library callers likewise need explicit live configuration
and `enable_live=True`; injecting the known real runner does not bypass this
guard. Arbitrary injected test runners are trusted executable Python code,
not an untrusted provider interface.

Automated tests use only injected responses or native fake CLI scripts,
disposable repositories and harmless real namespace commands. No real provider
generation or authentication calls are needed to test this milestone.

Independent Claude review of structured transport is required before Trial 0003.
Autonomous GitHub issue ingestion/readiness decisions, scheduling, retries,
roadmap selection, PR creation, issue closure, deployment and automatic
promotion remain outside this harness.
