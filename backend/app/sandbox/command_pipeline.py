"""
OMNI Sandbox — harmless command pipeline orchestrator (Phase 11 Stage 7).

Thin glue that runs ONE explicit argv command through the full sandbox chain:

    run_command -> command_result_to_sandbox_report
                -> project_sandbox_findings
                -> build_sandbox_findings_projection

It adds no new execution policy, no isolation, no tool knowledge, no file I/O,
and no mission/export integration. It does not import or call ``subprocess`` —
execution is delegated to ``run_command`` (the only subprocess boundary lives in
``execution.py``). This is NOT a full security sandbox; it inherits the honest
limitations documented in ``execution.py`` (no filesystem/network/resource
isolation, not safe for untrusted code).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

from backend.app.sandbox.command_report import command_result_to_sandbox_report
from backend.app.sandbox.execution import CommandResult, run_command
from backend.app.sandbox.export_projection import build_sandbox_findings_projection
from backend.app.sandbox.finding_projection import project_sandbox_findings
from backend.app.sandbox.report import SandboxReport


@dataclass
class CommandPipelineResult:
    """Bundle of every artifact produced by one command pipeline run.

    ``findings`` deliberately mirrors ``findings_projection["items"]`` — it is a
    debugging snapshot of the full chain, not a separate computation.
    """

    command_result: CommandResult
    report: SandboxReport
    findings: list[dict[str, Any]]
    findings_projection: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Deterministic dict with a fixed key order and fresh nested objects."""
        return {
            "schema": "omni.sandbox.command_pipeline.v1",
            "command_result": self.command_result.to_dict(),
            "sandbox_report": self.report.to_dict(),
            "findings": [dict(finding) for finding in self.findings],
            "findings_projection": dict(self.findings_projection),
        }


def run_command_pipeline(
    command: Union[list[str], tuple],
    *,
    cwd: Union[str, Path],
    timeout: float,
    env: Optional[dict[str, str]] = None,
    sandbox: str = "command",
    check_id: str = "command.exit",
    max_output_chars: Optional[int] = None,
) -> CommandPipelineResult:
    """Run one explicit argv command through the full sandbox chain.

    Delegates execution to ``run_command`` (argv-only, ``shell=False``, enforced
    timeout). All parameters mirror the underlying helpers; this orchestrator
    adds no defaults or policy of its own.
    """
    command_result = run_command(command, cwd=cwd, timeout=timeout, env=env)
    report = command_result_to_sandbox_report(
        command_result,
        sandbox=sandbox,
        check_id=check_id,
        max_output_chars=max_output_chars,
    )
    findings = project_sandbox_findings(report)
    findings_projection = build_sandbox_findings_projection(report)

    return CommandPipelineResult(
        command_result=command_result,
        report=report,
        findings=findings,
        findings_projection=findings_projection,
    )
