# TestCube Codex private runtime checkpoint

Issue: Give real Codex candidate generation private writable runtime/state
storage without exposing host credentials or trusted repository state.

Starting commit: `63408269fbb9d25b7c541d960156d99e0d936fdc` (clean).
Implementation branch: `omni/testcube-codex-private-state`.
This is an implementation handoff, not an independent approval.

## Historical evidence and diagnosis

`/home/honri/omni_testcube_trials/OMNI-TESTCUBE-TRIAL-0001` remains immutable
historical evidence with outcome `GENERATION_FAILED`. Its manifest's artifact
hashes were verified read-only. Neither candidate patch nor the task's bug
target was changed. No live trial was retried. Future attempts require a new
unique trial ID and human authorization after independent review.

Installed CLI: `codex-cli 0.153.4`, launched by the Node wrapper at
`/home/honri/.nvm/versions/node/v22.22.2/bin/codex`.
Host `HOME=/home/honri`; `CODEX_HOME` and XDG home overrides were unset, so
Codex used `/home/honri/.codex`. The original provider runner forwarded these
settings unchanged. Its read-only host root left only `/tmp` and `/run` as
writable scratch. Preflight and generation already shared that mount builder;
**the mismatch was what they exercised**, not different mount implementations.
Login/version success did not establish writable Codex runtime storage.

Before implementation, network-disabled syscall probes ran only `login status`,
`features list`, and `exec --help` in the original generation namespace.
File-operation tracing (no reads/writes of credential contents in trace output)
showed:

- Read-only open of the host `auth.json` during login and feature inspection.
- `chmod(CODEX_HOME/tmp/arg0, 0700)` failed with `EROFS`, while the harmless
  commands still exited successfully.
- With only a read-only auth bind in an otherwise empty tmpfs Codex home,
  login still succeeded. Codex created `tmp/arg0/codex-arg0…`, opened its `.lock`
  with `O_RDWR|O_CREAT`, and created its runtime aliases.

This verifies the missing writable-state class and the minimum file-auth
artifact for this installation. The exact fatal operation during Trial 0001's
`exec` was not retraced: no model-generation invocation was made, and the
harmless CLI commands treat the alias failure as a warning. The fake native CLI
regression reproduces login/version passing followed by `EROFS` at a required
runtime write. No unobserved session/database filename is assumed by the fix.

A separate disposable Git fixture accepted a valid text hunk containing
`index 1234567..89abcde 100644` with `git apply --index --binary
--whitespace=error-all -` (exit 0, expected resulting text).
**NON_BLOCKING**. No patch-byte canonicalization, patch-contract, collector,
or arbiter change was made.

## Implementation and supported boundary

`omni/testcube/codex_runtime.py` discovers canonical absolute HOME/state paths
and requires a regular, non-symlink `auth.json`. Missing auth, unsupported
paths, and source/archive overlaps fail closed. Only the verified file-backed
auth mode is supported; keyring-only and environment-key-only installations
require a separately reviewed adaptation. No credential directory is copied,
no credential bytes are logged, and no credential-content hashes are recorded.

For every Codex subprocess, `BoundedProviderRunner` creates a new Bubblewrap
namespace with a mode-0700 tmpfs at `/run/testcube-codex`. `CODEX_HOME` points
there; XDG config/state/cache homes also point underneath it. Host HOME remains
read-only. The sole auth artifact is bound read-only into private state, and
the original host Codex directory is masked with an empty read-only mount.
Unused provider API-key environment variables and Claude configuration paths
are removed from the Codex namespace. Other host filesystem visibility is the
existing read-only provider boundary; this change does not claim general host
secret-read isolation.

The private path is the same string across processes but has distinct tmpfs
storage per namespace. No private state is shared or copied out. Its lifetime
ends with the namespace. The existing process runner owns timeout, output
limits and subprocess cleanup. Claude's mount construction is unchanged.

Both preflight and generation call `CandidateProvider._run`, which selects the
same Codex runtime discovery, mount construction, and trusted in-namespace
entrypoint. Before exec, that guard checks read-only mount flags for HOME,
host state, source, Git metadata and auth; checks the output root is empty and
on a separate filesystem; opens auth read-only without inspecting its contents;
and actually creates a private directory, file, lock and symlink and fsyncs.
Host write probes use mount flags so a broken layout is rejected without
mutating the host. The guard also runs again for generation, closing drift
between preflight and process startup.

Login status explicitly selects file auth. Version and `features list` run in
the same guarded namespace; a failed, timed-out or oversized startup check
cannot yield a ready preflight. Generation retains read-only sandbox,
ephemeral mode, ignored user config/rules, disabled multi-agent/apps/hooks and
masked ancestor/project `.codex/config.toml`. The private home receives no
host configuration. A final network-disabled installed-CLI check reported
`CODEX_READY`, version `0.153.4`, and zero generation calls; the exact generation
argument vector with `--help` exited 0 without a read-only warning.

## Adversarial acceptance mapping

| # | Question | Finding / evidence |
|---|---|---|
| 1 | Write trusted OMNI? | No. Source RO mount and guard; native attempts to overwrite source/Git config fail. |
| 2 | Write host HOME? | No. RO mount and guard; native write attempt fails. |
| 3 | Write host Codex/auth state? | No. Original state masked RO, auth bind RO; writes/unlink fail; bytes, inventory, mode, ownership, inode, mtime and ctime snapshots identical (atime excluded). |
| 4 | Read required authentication? | Yes. Installed CLI login succeeds offline with only the verified file; fake reads its synthetic artifact. |
| 5 | Create private runtime state? | Yes. Guard exercises writes/lock/symlink; native fake creates session/cache/config/log/lock files. |
| 6 | Unique per invocation? | Yes. Every invocation begins without prior private files and receives a fresh tmpfs. |
| 7 | A read B's private state? | No. Native peer checks run in both orders; fresh PID, /tmp and /run views. |
| 8 | B read A's private state? | No. Same peer tests; entire external output root masked. |
| 9 | Private state enter archive? | No filesystem publication route; native regression scans all durable files for runtime/auth sentinels and filenames. Deliberate stdout disclosure has the same limitation as row 17. |
| 10 | Project config enable authority? | No. Native fixture supplies enabled multi-agent/apps/hooks config and sees an empty masked file; original CLI restrictions retained. |
| 11 | Preflight accept unwritable state? | No. Broken private mount rejects before CLI; generation rechecks after a successful preflight. This is structural compatibility, not a guarantee of future network/auth/model success. |
| 12 | Fake provider bypass mounts? | Native fake executable cannot. Arbitrary injected Python runners remain trusted test/operator code, not a security boundary. |
| 13 | Codex read-only sandbox? | Preserved; argv and native CLI assertions. |
| 14 | Source mounted read-only? | Yes; mount inspection and native write failures. |
| 15 | Trial output hidden? | Yes; guard, native empty-root checks, and deliberate archive-unmask rejection. |
| 16 | Output still patch-only? | Only validated patch bytes reach the unchanged collector. Existing raw candidate JSON remains non-authoritative audit data. |
| 17 | Credentials in stdout/stderr archives? | No auth/preflight output or generation stderr is archived. Existing raw generation stdout is archived: a malicious CLI (or a model deliberately reading and echoing its accessible auth) could disclose it. No output secret-filter guarantee is claimed or introduced. |
| 18 | Automated tests make model calls? | No. Added native executables and auth are synthetic; real CLI checks were explicitly manual and non-model. |
| 19 | Retry authority? | None. Per-instance max generation count remains 1; harness retries remain 0. |
| 20 | Promotion authority? | None. No collector/arbiter/control authority added; independent review and new human authorization remain required. |

## Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_testcube_candidate_harness.py -q`: **87 passed**.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_frontier_codex_provider.py tests/test_sandbox_execution.py tests/test_sandbox_limited_launcher.py tests/test_sandbox_resource_policy.py tests/test_testcube_collector.py tests/test_testcube_arbiter.py -q`: **473 passed** in 60.50s.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests -q`: **3303 passed, 2 warnings** in 102.56s. Warnings concern Python 3.10 support in Google API Core and the deprecated `google.generativeai` package; neither is changed here.
- `git diff --check`: clean. Final changed-file inspection: only the provider adapter, new Codex runtime module, harness regressions, and this handoff. Collector, arbiter, candidate target and Trial 0001 are unchanged.

Native collector isolation requires running tests outside the enclosing
workspace sandbox. The initial restricted run had 8 collector setup failures
and 76 passes; an unrestricted run exposed a fixture sentinel embedded in
archived source (1 failure, 83 passes). The fixture was corrected to construct
its sentinel at runtime; the archive assertion was retained. Subsequent runs
passed (84 tests before the final three additional checks, then 87).

Remaining review focus: mount ordering, file-auth-only fail-closed behavior,
shared guard coverage, and the pre-existing stdout/host-read trust limitations
above. No guarantee about successful billed generation is inferred from these
non-model checks. Independent Claude review is required before a new live
attempt. Real Claude model calls: **0**. Real Codex model-generation calls: **0**.
