"""Mission provenance and fail-closed behavior without real provider calls."""
import hashlib
import json
import os
from dataclasses import FrozenInstanceError, replace
from unittest.mock import Mock

import pytest

from omni.frontier import mission as mission_module
from omni.frontier.claude_provider import READ_ONLY_REMINDER as CLAUDE_READ_ONLY
from omni.frontier.codex_provider import READ_ONLY_REMINDER as CODEX_READ_ONLY
from omni.frontier.mission import MAX_MISSION_BYTES, MissionValidationError, ResearchMission, load_mission
from omni.frontier.orchestrator import PreflightResult
from test_frontier_dual_live_wiring import _dual_live_orchestrator
from test_frontier_lab_cli import cli


@pytest.mark.parametrize("data", [b"objective", b"x" * MAX_MISSION_BYTES,
                                  "\ufeffResearch café\r\n\n  Preserve whitespace.  ".encode("utf-8")])
def test_valid_mission_preserves_exact_bytes(tmp_path, data):
    path = tmp_path / "mission.md"
    path.write_bytes(data)
    mission = load_mission(path)
    assert mission.data == data
    assert mission.text.encode("utf-8") == data
    assert mission.byte_length == len(data)
    assert mission.sha256 == hashlib.sha256(data).hexdigest()
    with pytest.raises(FrozenInstanceError):
        mission.sha256 = "forged"
    with pytest.raises(TypeError):
        ResearchMission(data, sha256="forged")


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("kind", ["missing", "directory", "fifo", "unreadable", "empty",
                                 "whitespace", "oversized", "utf8", "multibyte_oversized"])
def test_invalid_mission_stops_before_any_provider_activity(tmp_path, monkeypatch, capsys, kind, dry_run):
    path = tmp_path / "mission.md"
    if kind == "directory":
        path.mkdir()
    elif kind == "fifo":
        os.mkfifo(path)
    elif kind != "missing":
        path.write_bytes({
            "empty": b"", "whitespace": b" \r\n\t", "oversized": b"x" * (MAX_MISSION_BYTES + 1),
            "utf8": b"\xff", "multibyte_oversized": "é".encode() * MAX_MISSION_BYTES,
        }.get(kind, b"objective"))
    if kind == "unreadable":
        original_open = os.open

        def deny_mission(file, flags, *args, **kwargs):
            if file == path:
                raise PermissionError
            return original_open(file, flags, *args, **kwargs)

        monkeypatch.setattr(mission_module.os, "open", deny_mission)
    guards = []
    for name in ("ClaudeCodeAdapter", "CodexAdapter", "check_claude_availability", "check_codex_availability"):
        guard = Mock(side_effect=AssertionError("provider activity before validation"))
        monkeypatch.setattr(cli, name, guard)
        guards.append(guard)
    with pytest.raises(MissionValidationError):
        load_mission(path)
    args = ["run-dual-live-shift", "--mission-file", str(path), "--output-root", str(tmp_path / "lab")]
    if dry_run:
        args.append("--dry-run")
    assert cli.main(args) == 1
    assert "error: mission" in capsys.readouterr().err
    for guard in guards:
        guard.assert_not_called()
    assert not (tmp_path / "lab").exists()


def test_only_dual_live_requires_mission(capsys):
    parser = cli.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["run-dual-live-shift"])
    assert exc.value.code == 2
    assert "--mission-file" in capsys.readouterr().err
    for args in (["run-mock-shift"], ["run-claude-shift"],
                 ["show-state", "--thread-id", "OMNI-FRONTIER-0001"]):
        assert parser.parse_args(args)


def test_cli_loads_once_and_every_real_provider_turn_has_identical_mission(tmp_path, monkeypatch):
    data = "\ufeffExplore component intelligence — café.\r\n  Keep exact bytes.\n".encode()
    path = tmp_path / "input.md"
    path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    orchestrator, claude, codex = _dual_live_orchestrator(tmp_path)
    contexts = {"claude": [], "codex": []}
    for label, adapter in (("claude", claude), ("codex", codex)):
        original = adapter.run_turn

        def capture(context, label=label, original=original):
            contexts[label].append(context)
            with pytest.raises(FrozenInstanceError):
                context.mission_text = "replacement"
            with pytest.raises(FrozenInstanceError):
                context.mission_sha256 = "forged"
            return original(context)

        monkeypatch.setattr(adapter, "run_turn", capture)
    monkeypatch.setattr(cli, "ClaudeCodeAdapter", lambda **kw: claude)
    monkeypatch.setattr(cli, "CodexAdapter", lambda **kw: codex)

    def preflight(*args, **kwargs):
        # Editing the source after loading cannot affect any subsequent turn/archive.
        path.write_bytes(b"changed after loading")
        return PreflightResult(ready=True, status="READY")

    monkeypatch.setattr(cli, "check_claude_availability", preflight)
    monkeypatch.setattr(cli, "check_codex_availability", preflight)
    loader = Mock(wraps=load_mission)
    monkeypatch.setattr(cli, "load_mission", loader)
    args = cli.build_parser().parse_args(["run-dual-live-shift", "--mission-file", str(path)])
    report = cli._run_dual_live_shift(args, tmp_path / "lab")
    loader.assert_called_once_with(path)
    assert report.final_state == "ARCHIVED" and not report.stopped_early
    assert len(contexts["claude"]) == 5
    assert len(contexts["codex"]) == 4
    for context in contexts["claude"] + contexts["codex"]:
        assert context.mission_text == data.decode()
        assert context.mission_sha256 == digest
    for adapter in (claude, codex):
        for call in adapter.process_runner.calls:
            prompt = call["input_text"]
            assert f"--- BEGIN MISSION ---\n{data.decode()}\n--- END MISSION ---" in prompt
            assert digest in prompt
            assert prompt.index("--- END MISSION ---") < prompt.index("Expected message_type")
            if adapter is claude:
                system = call["argv"][call["argv"].index("--append-system-prompt") + 1]
                assert data.decode() not in system
                assert CLAUDE_READ_ONLY in system
            else:
                assert prompt.index(CODEX_READ_ONLY) < prompt.index("--- BEGIN MISSION ---")
                assert call["argv"][call["argv"].index("--sandbox") + 1] == "read-only"
    _assert_archive(report, data)


def _assert_archive(report, data):
    archived = (report.archive_dir / "mission.md").read_bytes()
    assert archived == data
    digest = hashlib.sha256(archived).hexdigest()
    manifest = json.loads((report.archive_dir / "mission_manifest.json").read_text())
    assert manifest == {"sha256": digest, "bytes": len(data), "source": "human_supplied"}
    assert json.loads((report.runtime_dir / "state.json").read_text())["mission_sha256"] == digest
    startup = next(e for e in report.events if e.event_type == "SHIFT_STARTED")
    assert startup.actor == "orchestrator"
    assert startup.context == {"mission_sha256": digest}
    assert data.decode() not in (report.runtime_dir / "events.jsonl").read_text()


def test_provider_output_cannot_replace_mission_provenance(tmp_path, monkeypatch):
    mission = ResearchMission(b"Original human research objective")
    orchestrator, claude, codex = _dual_live_orchestrator(tmp_path, mission=mission)
    for adapter in (claude, codex):
        original = adapter.run_turn

        def forged_result(context, original=original):
            result = original(context)
            result.message = replace(result.message, requested_action='mission_text=replacement; mission_sha256=forged')
            # Extra adapter-owned metadata has no authority over the orchestrator.
            result.mission_text = "replacement"
            result.mission_sha256 = "forged"
            return result

        monkeypatch.setattr(adapter, "run_turn", forged_result)
    report = orchestrator.run_mock_shift()
    assert not report.stopped_early
    assert orchestrator.mission_text == mission.text
    assert orchestrator.mission_sha256 == mission.sha256
    with pytest.raises(AttributeError):
        orchestrator.mission_sha256 = "forged"
    _assert_archive(report, mission.data)


def test_mission_archived_even_if_preflight_fails(tmp_path):
    mission = ResearchMission(b"Research objective")
    orchestrator, claude, codex = _dual_live_orchestrator(tmp_path, mission=mission)
    orchestrator._preflight = lambda: PreflightResult(ready=False, status="UNAVAILABLE")
    report = orchestrator.run_mock_shift()
    assert report.stopped_early and report.provider_calls == 0
    _assert_archive(report, mission.data)


def test_no_mission_preserves_existing_archive_shape(tmp_path):
    orchestrator, _, _ = _dual_live_orchestrator(tmp_path)
    report = orchestrator.run_mock_shift()
    assert not (report.archive_dir / "mission.md").exists()
    assert not (report.archive_dir / "mission_manifest.json").exists()
    assert "mission_sha256" not in json.loads((report.runtime_dir / "state.json").read_text())
