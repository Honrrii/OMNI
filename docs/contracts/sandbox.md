# OMNI Sandbox — architecture & contract

Status: stable, additive (OMNI Phase 11, checkpoint at Stage 9A)

> **Read this first:** The OMNI Sandbox is a deterministic *verification harness*
> and a *controlled command-execution boundary*. It is **NOT a security
> sandbox** — see [Not a security sandbox](#not-a-security-sandbox). It does not
> yet run real external tools (colcon, KiCad, ROS2), and the execution boundary
> must be hardened before it ever does.

## Overview

The sandbox lives entirely under `backend/app/sandbox/`. It is additive,
standalone, and not wired into the mission runtime or export pipeline. Every
public surface is a pure function or a small dataclass with a deterministic
`to_dict()` (no timestamps, no UUIDs, no randomness), so the same input always
produces a byte-identical dictionary.

There are two paths that converge on the same normalized finding shape:

```
Pure check path
  run_sandbox(name, inputs)              backend/app/sandbox/runner.py
    -> SandboxReport                     backend/app/sandbox/report.py
       (omni.sandbox.report.v1)
  checks: units_math · dimensional_consistency · equation_sanity · artifact_shape
                                         backend/app/sandbox/checks/*.py

Execution path
  run_command(argv, cwd, timeout, env)   backend/app/sandbox/execution.py
    -> CommandResult                     (the ONLY subprocess boundary)
  command_result_to_sandbox_report(...)  backend/app/sandbox/command_report.py
    -> SandboxReport

Shared downstream
  project_sandbox_findings(report)       backend/app/sandbox/finding_projection.py
    -> list of normalized finding items
  build_sandbox_findings_projection(...) backend/app/sandbox/export_projection.py
    -> envelope (omni.sandbox.findings_projection.v1)

End-to-end orchestrator
  run_command_pipeline(argv, ...)        backend/app/sandbox/command_pipeline.py
    -> CommandPipelineResult (omni.sandbox.command_pipeline.v1)
```

## 1. Current sandbox chain (file map)

**Pure report/check path**
- `backend/app/sandbox/report.py` — `SandboxCheckResult`, `SandboxReport` dataclasses.
- `backend/app/sandbox/runner.py` — `run_sandbox(name, inputs)`; explicit dispatch, unknown name → safe `skipped` report.
- `backend/app/sandbox/checks/units_math.py` — mass-balance check.
- `backend/app/sandbox/checks/dimensional_consistency.py` — declared-vs-expected dimension check.
- `backend/app/sandbox/checks/equation_sanity.py` — left-vs-right equality via a safe AST arithmetic evaluator (no `eval`/`exec`).
- `backend/app/sandbox/checks/artifact_shape.py` — required-field/primitive-type check.

**Projection path**
- `backend/app/sandbox/finding_projection.py` — `project_sandbox_check_result(...)`, `project_sandbox_findings(report)`.

**Export envelope path**
- `backend/app/sandbox/export_projection.py` — `build_sandbox_findings_projection(report)`.

**Execution path**
- `backend/app/sandbox/execution.py` — `CommandResult`, `run_command(...)`. The only file permitted to import/call `subprocess`.
- `backend/app/sandbox/command_report.py` — `command_result_to_sandbox_report(...)`.
- `backend/app/sandbox/command_pipeline.py` — `CommandPipelineResult`, `run_command_pipeline(...)`.

## 2. Schemas and shapes

Three stable schema strings exist:

- `omni.sandbox.report.v1` — a raw sandbox report.
- `omni.sandbox.findings_projection.v1` — the additive findings projection envelope.
- `omni.sandbox.command_pipeline.v1` — the end-to-end command pipeline bundle.

### `SandboxCheckResult` (`report.py`)
| Field | Type | Notes |
| --- | --- | --- |
| `check_id` | str | e.g. `units.mass_balance`, `command.exit`. |
| `ok` | bool | `False` marks a finding-worthy outcome. |
| `severity` | str | `info` / `warning` / `error` (lowercased downstream). |
| `message` | str | Human-readable. |
| `expected` | str \| None | Stable string. |
| `actual` | str \| None | Stable string. |
| `file` | str \| None | Associated file when relevant, else `None`. |
| `metadata` | dict | Per-instance (default-factory); source-specific. |

`to_dict()` emits these keys in fixed order with a shallow-copied `metadata`.

### `SandboxReport` (`report.py`) — `omni.sandbox.report.v1`
| Field | Type | Notes |
| --- | --- | --- |
| `schema` | str | `"omni.sandbox.report.v1"`. |
| `sandbox` | str | Sandbox name (e.g. `units_math`, `command`). |
| `status` | str | `passed` / `completed` / `skipped`. |
| `checks` | list | List of `SandboxCheckResult`, order preserved. |
| `metadata` | dict | Optional, source-specific. |

Raw reports carry **no** `findings` or `findings_projection` key — projection is always layered on top by a separate helper, never embedded.

### Normalized finding item (`finding_projection.py`)
Reuses the documented Phase 10 13-key item shape (see
`docs/contracts/findings_projection.md`):

`id, code, source, category, severity, status, message, recommendation,
related_ids, file, evidence_ids, requires_human_review, metadata`

Sandbox mapping specifics:
- `code` = the check's `check_id`.
- `source` = `sandbox_<name>` (fallback `sandbox` when the name is empty/None).
- `category` = `"sandbox"`; `status` = `"open"`.
- `expected`/`actual` (which have no slot in the item shape) are routed into
  `metadata`, alongside `origin="SandboxCheckResult"`, `sandbox`, and the source
  check's metadata under `metadata["check_metadata"]`.

Only checks with `ok is False` project; passing/skipped reports project to `[]`.

### Sandbox findings projection envelope (`export_projection.py`) — `omni.sandbox.findings_projection.v1`
| Key | Value |
| --- | --- |
| `schema` | `"omni.sandbox.findings_projection.v1"` |
| `source` | `sandbox_<name>` (fallback `sandbox`) |
| `source_schema` | `"omni.sandbox.report.v1"` |
| `origin_fields` | `["checks"]` |
| `count` | `len(items)` |
| `items` | `project_sandbox_findings(report)` |

This mirrors the documented Phase 10 envelope vocabulary
(`schema`/`source`/`origin_fields`/`count`/`items`) plus an additive
`source_schema` provenance key.

### `CommandResult` (`execution.py`)
| Field | Type | Notes |
| --- | --- | --- |
| `command` | list[str] | argv echoed back. |
| `returncode` | int \| None | `None` on timeout. |
| `stdout` | str | Captured. |
| `stderr` | str | Captured. |
| `timed_out` | bool | `True` iff the timeout fired. |
| `timeout_seconds` | float | The configured limit (an input echo), **not** measured wall-clock time. |

### Command report mapping (`command_report.py`)
`command_result_to_sandbox_report(result, *, sandbox="command",
check_id="command.exit", max_output_chars=None)` produces a one-check report:

| Outcome | report `status` | `ok` | `severity` | `message` | `expected`/`actual` |
| --- | --- | --- | --- | --- | --- |
| `returncode == 0`, not timed out | `passed` | `True` | `info` | command completed successfully | `0`/`0` |
| `returncode != 0`, not timed out | `completed` | `False` | `warning` | command exited with nonzero status | `0`/`str(returncode)` |
| timed out | `completed` | `False` | `error` | command timed out | `0`/`timeout` |

Metadata preserves `command`, `returncode`, `timed_out`, `timeout_seconds`,
`stdout`, `stderr`, plus original `stdout_len`/`stderr_len` and
`stdout_truncated`/`stderr_truncated` flags. `max_output_chars` is optional,
post-capture truncation (default `None` = verbatim; negative is rejected).

### `CommandPipelineResult` (`command_pipeline.py`) — `omni.sandbox.command_pipeline.v1`
Holds the live `command_result`, `report`, `findings`, and
`findings_projection`. `to_dict()` returns:

| Key | Value |
| --- | --- |
| `schema` | `"omni.sandbox.command_pipeline.v1"` |
| `command_result` | `CommandResult.to_dict()` |
| `sandbox_report` | `SandboxReport.to_dict()` |
| `findings` | fresh copy of the projected findings list |
| `findings_projection` | the envelope dict |

Invariant: `findings == findings_projection["items"]` and
`findings_projection["count"] == len(findings)`.

## 3. Safety boundaries currently enforced

These are pinned by tests, not just convention:

- **Subprocess is confined to `backend/app/sandbox/execution.py`.** Every other
  sandbox file is forbidden from importing `subprocess` or calling
  `subprocess.run` — AST guard in `tests/test_sandbox_runner.py`.
- **`shell=True` is banned everywhere** in the sandbox package — positive AST
  assertion in `tests/test_sandbox_runner.py`.
- **`os.system` and `os.popen` are banned** (along with `subprocess.Popen`,
  `.call`, `.check_call`, `.check_output`) in every sandbox file, including
  `execution.py` — `tests/test_sandbox_runner.py`.
- **Command input is argv-only.** Strings, empty commands, and non-string
  elements are rejected; there is no `shell` parameter — `tests/test_sandbox_execution.py`.
- **Default environment is minimal and deterministic** (`PATH=/usr/bin:/bin`,
  `LC_ALL=C`, `LANG=C`); the parent `os.environ` is **not** inherited. A parent
  secret is proven not to leak to the child — `tests/test_sandbox_execution.py`.
- **Timeout is enforced;** on timeout the child is killed (best-effort process
  group), `returncode=None`, `timed_out=True` — `tests/test_sandbox_execution.py`.
- **Working directory is caller-provided;** child file writes are verified to
  stay inside the provided directory — `tests/test_sandbox_execution.py`,
  `tests/test_sandbox_command_pipeline.py`.
- **Deterministic `to_dict()` surfaces** (no timestamps/UUIDs/measured duration)
  — `tests/test_sandbox_report.py`, `tests/test_sandbox_command_report.py`,
  `tests/test_sandbox_command_pipeline.py`.
- **Raw reports are never mutated with `findings`/`findings_projection`.**
  Projection is layered, not embedded — `tests/test_sandbox_finding_projection.py`,
  `tests/test_sandbox_export_projection.py`.

## Not a security sandbox

**The current sandbox is process-level confinement at best. It is NOT a security
sandbox.** It does **not** provide any of the following:

- filesystem jail (the working directory is a convention, not a chroot)
- network isolation (a child can open sockets freely)
- memory limits
- CPU limits
- file-descriptor limits
- process-count limits
- seccomp filtering
- container isolation
- protection from untrusted code
- guaranteed containment of grandchild processes
- executable allowlisting
- bounded output capture **at execution time**

Additional honest caveats:
- Stage 6 output truncation (`max_output_chars`) is **post-capture** — it
  shrinks what is stored in the report but does **not** prevent memory pressure
  from a child that floods stdout/stderr, because `execution.py` uses
  `subprocess.run(capture_output=True)`, which buffers all output in memory
  before truncation can apply.
- Before any colcon / KiCad / ROS2 execution, OMNI needs the execution
  hardening described below. Do not run real tools through this boundary as-is.

## 4. Required hardening before real tools

The following are prerequisites before any real external tool is executed:

- **Output cap during capture** — stream and hard-limit stdout/stderr with
  kill-on-exceed, before unbounded in-memory buffering.
- **OS resource limits** — CPU seconds, address space/memory, max processes
  (`RLIMIT_NPROC`), and open files (`RLIMIT_NOFILE`).
- **stdin closed by default** (`stdin=DEVNULL`).
- **Stronger process-group reaping** — guaranteed termination of the whole
  session/grandchildren on timeout or abort.
- **Executable allowlist / tool gate** — a deliberate, tested opt-in before any
  non-harmless binary runs.
- **Artifact containment tests** — prove tool-generated files stay inside the
  provided working directory.
- **Controlled tool environment** — a minimal env sufficient to locate and run
  the tool, still without leaking parent secrets.
- **Possible future isolation** — containers, nsjail/firejail, or seccomp for
  any untrusted code or dangerous tool.

## 5. Non-goals

The current sandbox deliberately does **not** yet provide:

- mission/export integration (it is standalone; nothing wires it into the
  mission runtime or `export_manager.py`)
- frontend rendering
- a global findings model
- real-tool execution (colcon/KiCad/ROS2)
- artifact persistence (no files are written by the sandbox itself)
- security sandboxing (see above)
