"""Durable, single-writer Super-Build control plane.

Only trusted Python/terminal entry points are exposed. Candidate bytes enter
through TestCube collection; neither candidate JSON nor arbiter output is an
operator capability. The host, operator, Git and this machinery are trusted.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
import fcntl
import hashlib
import os
from pathlib import Path
import stat

from backend.app.sandbox.execution import run_command
from omni.testcube.candidate_models import strict_json
from omni.testcube.collector import (
    _changes, _read_regular, _scope_violations, _source_snapshot,
    arbitrate_collected, collect_and_evaluate,
)
from omni.testcube.collector_models import CollectionReceipt, canonical_bytes, digest
from omni.testcube.isolated_runner import write_new
from omni.superbuild.models import (
    SCHEMA, TERMINAL, SuperBuildCheckpoint, SuperBuildDecision, SuperBuildProject,
    SuperBuildState, SuperBuildWorkItem, identifier, require, sha, transition, work_from_dict,
)


class IntegrityError(RuntimeError):
    """Stop: durable state or filesystem observations disagree."""


class RecoveryRequired(IntegrityError):
    """An interrupted transaction needs offline human inspection; never guess."""


class ProjectBusy(RuntimeError):
    """Another reader/mutator holds the project lock."""


def _now():
    return datetime.now(timezone.utc).isoformat()


class _Git:
    """Same bounded subprocess wall and hardening as TestCube; no shell/hooks."""

    def text(self, cwd, *args):
        result = run_command([
            "/usr/bin/git", "--no-optional-locks", "-c", "core.hooksPath=/dev/null",
            "-c", "core.fsmonitor=false", "-c", "core.autocrlf=false",
            "-c", "core.attributesFile=/dev/null", "-c", "gc.auto=0",
            "-c", "maintenance.auto=false", "-c", "commit.gpgSign=false",
            *args,
        ], cwd=cwd, env={
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0", "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_ALLOW_PROTOCOL": "file", "GIT_OPTIONAL_LOCKS": "0",
        }, timeout=60, max_output_bytes=16 * 1024**2)
        if (result.returncode != 0 or result.timed_out or result.output_limit_exceeded or
                result.launcher_error):
            raise IntegrityError("trusted Git operation failed or was incomplete: " + args[0])
        return result.stdout


def _disjoint(a, b):
    return a != b and a not in b.parents and b not in a.parents


def _canonical_path(path):
    path = Path(path).absolute()
    require(path.resolve() == path, "symlink or noncanonical path")
    return path


def _fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _replace_json(path, value):
    temporary = path.with_name(path.name + ".next")
    write_new(temporary, canonical_bytes(value))
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def _sync_tree(root):
    """Flush project-owned bytes and directories before publishing their pointer."""
    directories = [root]
    for path in root.rglob("*"):
        require(not path.is_symlink(), "symlink in durable project data")
        if path.is_dir():
            directories.append(path)
        else:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                require(stat.S_ISREG(os.fstat(fd).st_mode), "nonregular durable project file")
                os.fsync(fd)
            finally:
                os.close(fd)
    for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True):
        _fsync_directory(directory)


def _json(path):
    _canonical_path(path)
    raw = _read_regular(path, 16 * 1024**2)
    data = strict_json(raw)
    require(canonical_bytes(data) == raw, "noncanonical durable JSON")
    return data


def _read_confirmation(prompt):
    # Closed stdin/piped model output is deliberately not an approval source.
    with open("/dev/tty", "r+", encoding="utf-8") as terminal:
        require(os.isatty(terminal.fileno()), "human decision requires a terminal")
        terminal.write(prompt)
        terminal.flush()
        return terminal.readline().rstrip("\n")


def _fault(stage):
    """Test seam for process interruptions; production never injects a fault."""


def _commit_message(decision):
    # Commit and journal bind exactly the same canonical human decision.
    return "SuperBuild checkpoint\n\n" + canonical_bytes(asdict(decision)).decode()


class SuperBuildBox:
    def __init__(self, root):
        self.root = _canonical_path(root)
        require(_disjoint(self.root, Path(__file__).resolve().parents[2]),
                "Super-Build storage must be outside trusted OMNI")
        self.git = _Git()

    def _path(self, project_id):
        identifier(project_id)
        require(project_id not in ("locks", "registry"), "reserved project ID")
        return self.root / project_id

    def _anchor(self, project_id):
        return self.root / "registry" / (project_id + ".json")

    @contextmanager
    def _lock(self, project_id):
        self._path(project_id)
        _canonical_path(self.root)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.root.stat()
        require(info.st_uid == os.getuid() and not info.st_mode & 0o077, "storage root must be private and operator-owned")
        locks = self.root / "locks"
        _canonical_path(locks)
        locks.mkdir(mode=0o700, exist_ok=True)
        fd = os.open(locks / project_id, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            require(stat.S_ISREG(os.fstat(fd).st_mode), "lock must be a regular file")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ProjectBusy(project_id) from exc
            yield
        finally:
            os.close(fd)

    @contextmanager
    def _transaction(self, project_id, operation):
        marker = self._path(project_id) / "transaction.json"
        if marker.exists():
            raise RecoveryRequired("interrupted transaction; human inspection required")
        write_new(marker, canonical_bytes({"operation": operation, "started_at": _now()}))
        yield
        # Any exception, SIGKILL or power loss before this point retains intent.
        marker.unlink()
        _fsync_directory(marker.parent)

    def create(self, *, project_id, title, description, source_repo, origin_commit):
        sha(origin_commit, 40)
        source = _canonical_path(source_repo)
        require(_disjoint(source, self.root), "workspace must be outside trusted source")
        with self._lock(project_id):
            root = self._path(project_id)
            require(not root.exists() and not self._anchor(project_id).exists(), "project ID is permanently single-use")
            require(self.git.text(source, "rev-parse", "--show-toplevel").strip() == str(source), "source must be repository root")
            before = _source_snapshot(source, self.git)
            require(before["clean"] and before["head"] == origin_commit, "source must be clean at the immutable origin")
            self._check_checkout(source, origin_commit, include_ignored=False)
            root.mkdir(mode=0o700)
            _fsync_directory(self.root)
            with self._transaction(project_id, "create"):
                workspace = root / "workspace"
                self.git.text(root, "clone", "--template=", "--no-local", "--no-hardlinks", "--no-checkout",
                              "--", str(source), str(workspace))
                self.git.text(workspace, "config", "--remove-section", "remote.origin")
                self.git.text(workspace, "checkout", "--detach", origin_commit)
                for ref in self.git.text(workspace, "for-each-ref", "--format=%(refname)").splitlines():
                    self.git.text(workspace, "update-ref", "-d", ref)
                self._check_checkout(workspace, origin_commit)
                _sync_tree(workspace)
                project = SuperBuildProject(project_id, title, description, origin_commit, str(source),
                    str(workspace), _now(), digest(_read_regular(workspace / ".git/config", 1024**2)))
                write_new(root / "project.json", canonical_bytes(asdict(project)))
                (root / "records").mkdir(mode=0o700)
                (root / "evidence").mkdir(mode=0o700)
                (root / "inputs").mkdir(mode=0o700)
                require(before == _source_snapshot(source, self.git), "trusted source changed during clone")
                self._publish(project, [], self._empty_state(project))
        return self.load(project_id)

    def _empty_state(self, project):
        return SuperBuildState(project.project_id, project.origin_commit, project.origin_commit,
                               digest(canonical_bytes(asdict(project))), (), (), ())

    def _publish(self, project, records, state):
        root = self._path(project.project_id)
        manifest = {"schema_version": SCHEMA, "project_digest": digest(canonical_bytes(asdict(project))),
                    "record_digests": [digest(canonical_bytes(r)) for r in records], "state": asdict(state)}
        _replace_json(root / "manifest.json", manifest)
        registry = self.root / "registry"
        _canonical_path(registry)
        registry.mkdir(mode=0o700, exist_ok=True)
        _replace_json(self._anchor(project.project_id), {
            "project_digest": manifest["project_digest"], "manifest_digest": digest(canonical_bytes(manifest)),
            "record_count": len(records), "tip": manifest["record_digests"][-1] if records else manifest["project_digest"],
        })
        _fsync_directory(root)
        _fsync_directory(self.root)

    def _append(self, project, records, kind, payload):
        payload = strict_json(canonical_bytes(payload))
        previous = digest(canonical_bytes(records[-1])) if records else digest(canonical_bytes(asdict(project)))
        record = {"sequence": len(records), "previous": previous, "kind": kind, "payload": payload}
        write_new(self._path(project.project_id) / "records" / f"{len(records):08d}.json", canonical_bytes(record))
        records.append(record)

    def _check_checkout(self, workspace, commit, *, include_ignored=True):
        require(self.git.text(workspace, "rev-parse", "HEAD").strip() == commit, "workspace wrong HEAD")
        status_args = ("--ignored",) if include_ignored else ()
        require(not self.git.text(workspace, "status", "--porcelain=v1", "-z", "--untracked-files=all", *status_args),
                "workspace dirty (including ignored files)")
        inventory = self.git.text(workspace, "ls-files", "-v", "-z").split("\0")
        require(inventory[-1] == "" and all(v.startswith("H ") for v in inventory[:-1]), "unsupported index flags")
        # Hash raw bytes, independent of index stat cache, filters and timestamps.
        for entry in self.git.text(workspace, "ls-tree", "-r", "-z", commit).split("\0"):
            if not entry:
                continue
            metadata, name = entry.split("\t", 1)
            mode, kind, blob = metadata.split()
            require(mode in ("100644", "100755") and kind == "blob", "unsupported tree mode")
            path = _canonical_path(workspace / name)
            raw = _read_regular(path, 64 * 1024**2)
            actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            require(blob == actual, "workspace content hash mismatch")
            require(bool(path.stat().st_mode & 0o111) == (mode == "100755"), "workspace file mode mismatch")

    def _check_workspace(self, project, state):
        workspace = _canonical_path(project.workspace_path)
        require(workspace == self._path(project.project_id) / "workspace", "workspace location mismatch")
        require(_disjoint(Path(project.trusted_source_path), self.root), "source/workspace overlap")
        gitdir = workspace / ".git"
        require(gitdir.is_dir() and not gitdir.is_symlink(), "workspace must own Git metadata")
        for path in gitdir.rglob("*"):
            require(not path.is_symlink(), "symlink in Git metadata")
        require(digest(_read_regular(gitdir / "config", 1024**2)) == project.workspace_config_digest,
                "workspace Git config changed")
        for relative in ("objects/info/alternates", "info/grafts", "info/attributes", "shallow", "commondir"):
            require(not (gitdir / relative).exists(), "unsupported Git indirection")
        require(self.git.text(workspace, "rev-parse", "--absolute-git-dir").strip() == str(gitdir), "foreign Git directory")
        require(not self.git.text(workspace, "remote") and not self.git.text(workspace, "for-each-ref"),
                "project workspace cannot have remotes or branches")
        require(_read_regular(gitdir / "HEAD", 128) == (state.accepted_project_commit + "\n").encode(), "HEAD must be detached")
        require(self.git.text(workspace, "cat-file", "-t", project.origin_commit).strip() == "commit", "missing origin")
        self._check_checkout(workspace, state.accepted_project_commit)

    def _evidence(self, project, work, payload):
        require(set(payload) == {"work_item_id", "receipt", "candidate_digests", "verdict"}, "invalid evidence record")
        data = payload["receipt"]
        receipt = CollectionReceipt(**(data | {"patch_sha256": tuple(data["patch_sha256"])}))
        expected = self._path(project.project_id) / "evidence" / work.work_item_id
        require(receipt.bundle_path == str(expected) and receipt.evaluation_id == work.work_item_id and
                receipt.base_revision == work.parent_accepted_commit, "wrong evidence parent/identity")
        inputs = self._path(project.project_id) / "inputs" / work.work_item_id
        require(receipt.patch_sha256 == tuple(digest(_read_regular(_canonical_path(inputs / slot),
                    work.collector_policy.max_patch_bytes)) for slot in ("A", "B")), "collector/input patch mismatch")
        arbitration = arbitrate_collected(receipt, work.collector_policy)
        require(arbitration.verdict == payload["verdict"], "arbiter record mismatch")
        actual = [digest(_read_regular(expected / f"candidate-{slot}/evidence.json", 16 * 1024**2)) for slot in ("A", "B")]
        require(actual == payload["candidate_digests"], "candidate digest mismatch")
        return receipt, arbitration

    def _replay(self, project, records, *, check_commits=True):
        state = self._empty_state(project)
        works, decisions, checkpoints, evidence = {}, [], [], {}
        pending_accept = None
        previous = state.accepted_checkpoint
        for index, record in enumerate(records):
            require(set(record) == {"sequence", "previous", "kind", "payload"} and
                    type(record["sequence"]) is int and record["sequence"] == index and record["previous"] == previous,
                    "broken append-only history")
            previous = digest(canonical_bytes(record))
            kind, payload = record["kind"], record["payload"]
            require(pending_accept is None or kind == "checkpoint", "acceptance requires next checkpoint")
            if kind == "work":
                work = work_from_dict(payload)
                require(work.project_id == project.project_id and work.status == "PENDING" and
                        work.work_item_id not in works and all(w.status in TERMINAL for w in works.values()),
                        "duplicate or concurrent work")
                require(work.parent_checkpoint == state.accepted_checkpoint and
                        work.parent_accepted_commit == state.accepted_project_commit, "wrong parent checkpoint")
                works[work.work_item_id] = work
            elif kind == "transition":
                require(set(payload) == {"work_item_id", "from", "to"}, "invalid transition record")
                work = works[payload["work_item_id"]]
                require(work.status == payload["from"] and payload["to"] not in
                        ("ACCEPTED", "REJECTED", "AWAITING_HUMAN_DECISION", "EVALUATING"), "transition requires authoritative record")
                transition(work.status, payload["to"])
                works[work.work_item_id] = replace(work, status=payload["to"])
            elif kind == "evidence":
                work = works[payload["work_item_id"]]
                transition(work.status, "AWAITING_HUMAN_DECISION")
                require(work.work_item_id not in evidence, "duplicate evidence")
                self._evidence(project, work, payload)
                evidence[work.work_item_id] = payload
                works[work.work_item_id] = replace(work, status="AWAITING_HUMAN_DECISION")
            elif kind == "evaluation":
                require(set(payload) == {"work_item_id", "patch_digests"} and type(payload["patch_digests"]) is list and
                        len(payload["patch_digests"]) == 2, "invalid input record")
                work = works[payload["work_item_id"]]
                transition(work.status, "EVALUATING")
                inputs = self._path(project.project_id) / "inputs" / work.work_item_id
                for slot, expected in zip(("A", "B"), payload["patch_digests"]):
                    sha(expected)
                    require(digest(_read_regular(_canonical_path(inputs / slot), work.collector_policy.max_patch_bytes)) == expected,
                            "input patch hash mismatch")
                works[work.work_item_id] = replace(work, status="EVALUATING")
            elif kind == "decision":
                decision = SuperBuildDecision(**payload)
                work = works[decision.work_item_id]
                require(work.status == "AWAITING_HUMAN_DECISION" and decision.project_id == project.project_id and
                        decision.parent_checkpoint == state.accepted_checkpoint == work.parent_checkpoint and
                        decision.parent_accepted_commit == state.accepted_project_commit == work.parent_accepted_commit,
                        "decision parent/status mismatch")
                supplied = evidence[work.work_item_id]
                receipt, arbitration = self._evidence(project, work, supplied)
                require(decision.evidence_digest == receipt.manifest_sha256, "wrong evidence digest")
                if decision.selected_candidate:
                    slot = decision.selected_candidate
                    i = ("A", "B").index(slot)
                    require(decision.candidate_digest == supplied["candidate_digests"][i] and
                            decision.patch_digest == receipt.patch_sha256[i], "wrong candidate/patch digest")
                    require(all(g.passed for g in arbitration.mandatory_gate_results if g.candidate_id == slot),
                            "human cannot accept gate-invalid candidate")
                    changes = _json(Path(receipt.bundle_path) / f"candidate-{slot}/changed-paths.json")
                    require(changes["touched_files"] and all(c["status"] == "M" for c in changes["changes"]),
                            "v0 acceptance requires existing-file modifications")
                    pending_accept = decision
                elif decision.decision == "REJECT_BOTH":
                    transition(work.status, "REJECTED")
                    works[work.work_item_id] = replace(work, status="REJECTED")
                decisions.append(decision)
            elif kind == "checkpoint":
                checkpoint = SuperBuildCheckpoint(**payload)
                require(pending_accept is not None, "checkpoint without human decision")
                decision = pending_accept
                require(payload == asdict(self._checkpoint(decision, checkpoint.accepted_project_commit)), "checkpoint decision bindings differ")
                if check_commits:
                    workspace = Path(project.workspace_path)
                    commit = checkpoint.accepted_project_commit
                    require(self.git.text(workspace, "show", "-s", "--format=%P", commit).strip() == state.accepted_project_commit,
                            "checkpoint ancestry mismatch")
                    require(self.git.text(workspace, "show", "-s", "--format=%B", commit).rstrip() == _commit_message(decision).rstrip(),
                            "checkpoint commit metadata mismatch")
                    message = self._path(project.project_id) / "inputs" / decision.work_item_id / "commit-message"
                    require(_read_regular(_canonical_path(message), 128 * 1024) == _commit_message(decision).encode(),
                            "commit message artifact mismatch")
                    self._verify_commit_patch(project, works[decision.work_item_id], decision, commit)
                work = works[decision.work_item_id]
                transition(work.status, "ACCEPTED")
                works[work.work_item_id] = replace(work, status="ACCEPTED")
                checkpoints.append(checkpoint)
                state = replace(state, accepted_project_commit=checkpoint.accepted_project_commit,
                                accepted_checkpoint=digest(canonical_bytes(payload)))
                pending_accept = None
            else:
                raise IntegrityError("unknown journal record")
        require(pending_accept is None, "uncommitted human acceptance")
        return replace(state, work_items=tuple(works.values()), checkpoints=tuple(checkpoints), decisions=tuple(decisions))

    def _load(self, project_id):
        root = _canonical_path(self._path(project_id))
        if (root / "transaction.json").exists():
            raise RecoveryRequired("interrupted transaction; preserve files for human inspection")
        project = SuperBuildProject(**_json(root / "project.json"))
        require(project.project_id == project_id, "project identity mismatch")
        manifest = _json(root / "manifest.json")
        anchor = _json(self._anchor(project_id))
        project_hash = digest(canonical_bytes(asdict(project)))
        require(set(manifest) == {"schema_version", "project_digest", "record_digests", "state"} and
                manifest["schema_version"] == SCHEMA and manifest["project_digest"] == project_hash,
                "manifest project binding mismatch")
        require(type(manifest["record_digests"]) is list, "invalid history index")
        require(canonical_bytes(anchor) == canonical_bytes({"project_digest": project_hash, "manifest_digest": digest(canonical_bytes(manifest)),
                "record_count": len(manifest["record_digests"]),
                "tip": manifest["record_digests"][-1] if manifest["record_digests"] else project_hash}),
                "registry anchor mismatch (tampering or interrupted publication)")
        records_dir = _canonical_path(root / "records")
        require(sorted(p.name for p in records_dir.iterdir()) == [f"{i:08d}.json" for i in range(anchor["record_count"])],
                "missing or extra history records")
        records = [_json(records_dir / f"{i:08d}.json") for i in range(anchor["record_count"])]
        require([digest(canonical_bytes(r)) for r in records] == manifest["record_digests"], "history hash mismatch")
        # Check config/HEAD before Git can process any attacker-modified metadata.
        basic = self._empty_state(project)
        basic = replace(basic, accepted_project_commit=manifest["state"]["accepted_project_commit"])
        self._check_workspace(project, basic)
        state = self._replay(project, records)
        require(canonical_bytes(asdict(state)) == canonical_bytes(manifest["state"]), "manifest differs from authoritative replay")
        require(not list(root.glob("*.next")), "incomplete manifest publication")
        return project, records, state

    def load(self, project_id):
        """Reconstruct and verify all durable state under the same mutation lock."""
        with self._lock(project_id):
            try:
                return self._load(project_id)[2]
            except (IntegrityError, ProjectBusy):
                raise
            except Exception as exc:
                raise IntegrityError("project verification failed: " + str(exc)) from exc

    def add_work_item(self, work):
        require(type(work) is SuperBuildWorkItem, "operator-defined work item required")
        with self._lock(work.project_id):
            project, records, state = self._load(work.project_id)
            require(work.parent_checkpoint == state.accepted_checkpoint and work.parent_accepted_commit == state.accepted_project_commit,
                    "wrong parent checkpoint")
            require(work.status == "PENDING" and all(w.status in TERMINAL for w in state.work_items) and
                    work.work_item_id not in {w.work_item_id for w in state.work_items}, "one active work item; IDs are single-use")
            with self._transaction(work.project_id, "add-work"):
                self._append(project, records, "work", asdict(work))
                self._publish(project, records, self._replay(project, records))
        return self.load(work.project_id)

    def advance(self, project_id, work_item_id, status):
        # Completion is exclusively owned by evidence/decision handling.
        require(status not in ("ACCEPTED", "REJECTED", "AWAITING_HUMAN_DECISION", "EVALUATING"), "reserved transition")
        with self._lock(project_id):
            project, records, state = self._load(project_id)
            work = next(w for w in state.work_items if w.work_item_id == work_item_id)
            transition(work.status, status)
            with self._transaction(project_id, "transition"):
                self._append(project, records, "transition", {"work_item_id": work_item_id, "from": work.status, "to": status})
                self._publish(project, records, self._replay(project, records))
        return self.load(project_id)

    def evaluate(self, project_id, work_item_id, *, patch_a, patch_b):
        """Synthetic rendered patches only; trusted TestCube collects real evidence.

        No external evidence or decision object can be submitted here. No provider
        runtime exists in v0. Caller paths are read once into private input files.
        """
        with self._lock(project_id):
            project, records, state = self._load(project_id)
            work = next(w for w in state.work_items if w.work_item_id == work_item_id)
            transition(work.status, "EVALUATING")
            patches = [_read_regular(Path(p), work.collector_policy.max_patch_bytes) for p in (patch_a, patch_b)]
            with self._transaction(project_id, "evaluate"):
                inputs = self._path(project_id) / "inputs" / work_item_id
                for slot, raw in zip(("A", "B"), patches):
                    write_new(inputs / slot, raw)
                self._append(project, records, "evaluation", {"work_item_id": work_item_id, "patch_digests": [digest(p) for p in patches]})
                result = collect_and_evaluate(source_repo=Path(project.workspace_path), patch_a=inputs / "A", patch_b=inputs / "B",
                    policy=work.collector_policy, output_root=self._path(project_id) / "evidence", cleanup=True)
                if result.arbitration is None or result.receipt is None:
                    self._append(project, records, "transition", {"work_item_id": work_item_id, "from": "EVALUATING", "to": "EVIDENCE_FAILED"})
                else:
                    receipt = result.receipt
                    _sync_tree(Path(receipt.bundle_path))
                    payload = {"work_item_id": work_item_id, "receipt": asdict(receipt),
                        "candidate_digests": [digest(_read_regular(Path(receipt.bundle_path) / f"candidate-{s}/evidence.json", 16 * 1024**2)) for s in ("A", "B")],
                        "verdict": result.arbitration.verdict}
                    # Canonical JSON arrays for replay and on-disk comparisons.
                    payload = strict_json(canonical_bytes(payload))
                    self._append(project, records, "evidence", payload)
                self._publish(project, records, self._replay(project, records))
        return self.load(project_id)

    @staticmethod
    def _checkpoint(decision, commit):
        return SuperBuildCheckpoint(decision.project_id, decision.work_item_id, decision.parent_checkpoint,
            decision.parent_accepted_commit, commit, decision.selected_candidate, decision.candidate_digest,
            decision.patch_digest, decision.evidence_digest, digest(canonical_bytes(asdict(decision))))

    def _verify_commit_patch(self, project, work, decision, commit):
        # Git's canonical tree delta binds every byte and mode in the accepted
        # commit to the exact staged result captured by the collector.
        bundle = self._path(project.project_id) / "evidence" / work.work_item_id
        operations = _json(bundle / f"candidate-{decision.selected_candidate}/operations.json")
        require(self.git.text(Path(project.workspace_path), "rev-parse", commit + "^{tree}").strip() == operations["index_tree"],
                "checkpoint tree differs from evaluated candidate")

    def decide(self, *, project_id, work_item_id, decision, operator, parent_checkpoint,
               parent_accepted_commit, evidence_digest, candidate_digest=None, patch_digest=None):
        """The only acceptance entry point: exact digest-bound human TTY confirmation."""
        selected = decision[-1] if type(decision) is str and decision.startswith("ACCEPT_") else None
        proposed = SuperBuildDecision(project_id, work_item_id, parent_checkpoint, parent_accepted_commit,
            evidence_digest, decision, selected, candidate_digest, patch_digest, operator, _now())
        with self._lock(project_id):
            project, records, state = self._load(project_id)
            # Validate *before* asking a human, using the same authoritative replay.
            record = {"sequence": len(records), "previous": digest(canonical_bytes(records[-1])),
                      "kind": "decision", "payload": asdict(proposed)}
            preview = records + [record]
            if selected:
                checkpoint = self._checkpoint(proposed, parent_accepted_commit)
                preview.append({"sequence": len(preview), "previous": digest(canonical_bytes(record)),
                                "kind": "checkpoint", "payload": asdict(checkpoint)})
            self._replay(project, preview, check_commits=False)
            token = f"{decision} {project_id}/{work_item_id} {digest(canonical_bytes(asdict(proposed)))}"
            prompt = canonical_bytes(asdict(proposed)).decode() + "\nType exactly to authorize this project-local decision:\n" + token + "\n> "
            require(_read_confirmation(prompt) == token, "human confirmation did not match")
            # Recheck all files after the human's potentially long pause.
            project, records, state = self._load(project_id)
            with self._transaction(project_id, "human-decision"):
                self._append(project, records, "decision", asdict(proposed))
                if selected:
                    _fault("before_candidate_application")
                    workspace = Path(project.workspace_path)
                    patch = self._path(project_id) / "evidence" / work_item_id / f"candidate-{selected}/patch.diff"
                    require(digest(_read_regular(patch, 128 * 1024)) == patch_digest, "patch changed before application")
                    self.git.text(workspace, "apply", "--check", "--index", "--binary", "--", str(patch))
                    _fault("during_candidate_application")
                    self.git.text(workspace, "apply", "--index", "--binary", "--whitespace=nowarn", "--", str(patch))
                    _fault("after_patch_before_commit")
                    work = next(w for w in state.work_items if w.work_item_id == work_item_id)
                    changes = _changes(workspace, parent_accepted_commit, self.git)
                    require(changes["touched_files"] and not _scope_violations(changes, work.collector_policy) and
                            all(c["status"] == "M" for c in changes["changes"]), "unsupported or out-of-scope application")
                    self.git.text(workspace, "diff", "--cached", "--check", parent_accepted_commit, "--")
                    staged = self.git.text(workspace, "write-tree").strip()
                    operations = _json(patch.parent / "operations.json")
                    require(staged == operations["index_tree"], "applied tree differs from evaluated candidate")
                    message = self._path(project_id) / "inputs" / work_item_id / "commit-message"
                    write_new(message, _commit_message(proposed).encode())
                    self.git.text(workspace, "-c", "user.name=OMNI SuperBuild", "-c", "user.email=superbuild@localhost",
                                  "-c", "core.fsync=committed", "commit", "--no-verify", "--cleanup=verbatim", "-F", str(message))
                    commit = self.git.text(workspace, "rev-parse", "HEAD").strip()
                    _fault("after_commit_before_manifest")
                    _sync_tree(workspace)
                    self._append(project, records, "checkpoint", asdict(self._checkpoint(proposed, commit)))
                new_state = self._replay(project, records)
                self._check_workspace(project, new_state)
                self._publish(project, records, new_state)
                _fault("after_manifest_update")
        return self.load(project_id)


def verify_superbuild_project(root, project_id):
    """Return verified reconstructed state, or fail closed with an exception."""
    return SuperBuildBox(root).load(project_id)
