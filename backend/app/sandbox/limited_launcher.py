"""
OMNI Sandbox — standalone resource-limit child launcher (Phase 11 Stage 9B-3B-1).

This is a tiny, self-contained launcher that applies OS resource limits to
itself and then replaces itself with an approved target command via
``os.execvp``. The executed tool inherits the limits and stays in the same
process/session group, so the parent's timeout, process-group termination,
closed stdin, and output capture continue to govern it unchanged.

INVOCATION — by absolute file path ONLY::

    python /abs/path/to/backend/app/sandbox/limited_launcher.py \
        --policy-json <json> -- <executable> [args...]

It must NOT be run as ``python -m backend.app.sandbox.limited_launcher``: the
sandbox runs children from an arbitrary caller-provided working directory with a
minimal environment that has no inherited ``PYTHONPATH``. Running by absolute
path puts only this file's directory on ``sys.path`` and needs no package
install. For the same reason this module imports the standard library ONLY and
never imports anything from ``backend.*`` (it intentionally re-validates the
six-field policy instead of importing ``ResourceLimits``).

DESIGN NOTES:
- Linux-only resource-limit enforcement; on platforms without the ``resource``
  module it fails closed (it never silently skips a requested limit).
- No ``preexec_fn`` (that would run Python post-fork in a possibly multithreaded
  parent and risk deadlock); limits are applied in this fresh single-threaded
  child before ``execvp``.
- No ``subprocess`` — this process becomes the target via ``execvp``.
- Setup failures occur strictly before ``execvp`` and exit with reserved codes,
  so the target never starts on a setup error.

OUT-OF-BAND STATUS HANDSHAKE (Phase 11 Stage 9B-3C-2):
When the parent passes an optional ``--status-fd <int>`` (an inherited write end
of a dedicated pipe, never stdout/stderr), this launcher reports its own outcome
through that fd so the parent never has to guess from the process return code:

- On ANY launcher-owned failure (bad args, bad/invalid policy, unsupported
  policy, failed limit application, failed ``execvp``) it writes a single
  deterministic ASCII token (see ``STATUS_*``) to the status fd before exiting
  with the matching reserved code.
- Immediately before ``os.execvp`` it marks the status fd close-on-exec, so a
  SUCCESSFUL exec closes it automatically — the parent then reads EOF with no
  payload (success) and the exec'd target never inherits the descriptor.

``--status-fd`` is OPTIONAL: omitting it preserves the original standalone
reserved-exit-code behavior for direct invocation and existing tests.

HONEST SECURITY NOTE — this is NOT a full security sandbox. Resource limits bound
CPU/memory/file-size/fd quotas; they provide no filesystem jail, no network
isolation, no seccomp/cgroups/container isolation, and no protection from
untrusted code.
"""
import json
import os
import sys

try:
    import resource
except ImportError:  # pragma: no cover - non-Linux platforms (e.g. Windows)
    resource = None


# Reserved launcher setup-failure exit codes. Chosen in an uncommon high range
# (avoiding 0/1/2 and the shell's 126/127) so a launcher setup failure is
# distinguishable from an ordinary target exit code.
EXIT_BAD_ARGS = 119
EXIT_BAD_POLICY = 118
EXIT_UNSUPPORTED = 117
EXIT_APPLY_FAILED = 116
EXIT_EXEC_FAILED = 115


# Deterministic ASCII status tokens written to the optional ``--status-fd`` pipe
# (Stage 9B-3C-2). Each maps one-to-one to a reserved exit code above and to the
# parent's ``launcher_error`` name, so a launcher failure is reported out-of-band
# and is never confused with a target's own exit code. A successful ``execvp``
# writes NOTHING (the fd is closed-on-exec -> parent reads EOF).
STATUS_BAD_ARGS = "bad_launcher_args"
STATUS_BAD_POLICY = "invalid_resource_policy"
STATUS_UNSUPPORTED = "unsupported_resource_policy"
STATUS_APPLY_FAILED = "resource_limit_apply_failed"
STATUS_EXEC_FAILED = "launcher_exec_failed"
# Emitted when the launcher cannot safely complete the status handshake itself
# (e.g. it fails to make the status fd close-on-exec before execvp). Reported as
# an authoritative launcher error; the target is never started in this case.
STATUS_PROTOCOL_ERROR = "launcher_status_protocol_error"


# The exact policy field set, duplicated from ``ResourceLimits`` on purpose: this
# launcher must run standalone (by absolute path, minimal env) and cannot import
# ``backend.app.sandbox.resource_policy``.
POLICY_FIELDS = (
    "cpu_seconds",
    "address_space_bytes",
    "file_size_bytes",
    "open_files",
    "process_count",
    "core_size_bytes",
)

# Fields whose enforcement is deferred in this stage. Requesting either of these
# fails closed (EXIT_UNSUPPORTED) rather than being silently ignored.
_DEFERRED_FIELDS = ("address_space_bytes", "process_count")


class LauncherArgsError(Exception):
    """Invalid launcher CLI arguments -> EXIT_BAD_ARGS."""


class LauncherPolicyError(Exception):
    """Invalid policy JSON/schema/values -> EXIT_BAD_POLICY."""


class LauncherUnsupportedError(Exception):
    """Platform/limit not supported in this stage -> EXIT_UNSUPPORTED."""


def extract_status_fd(argv):
    """Split an optional leading ``--status-fd <int>`` off ``argv``.

    Returns ``(status_fd, rest)`` where ``status_fd`` is ``None`` when the flag
    is absent (standalone/back-compat mode) or a non-negative integer otherwise.
    ``rest`` is the remaining argv to hand to ``parse_args``. Raises
    ``LauncherArgsError`` if the flag is present but malformed.
    """
    if argv and argv[0] == "--status-fd":
        if len(argv) < 2:
            raise LauncherArgsError("missing value for '--status-fd'.")
        try:
            status_fd = int(argv[1])
        except (TypeError, ValueError):
            raise LauncherArgsError("'--status-fd' value must be an integer.")
        if status_fd < 0:
            raise LauncherArgsError("'--status-fd' must be a non-negative integer.")
        return status_fd, argv[2:]
    return None, argv


def _emit_status(status_fd, token):
    """Best-effort single-token write to the parent's status pipe; never raise.

    Called only on a launcher-owned failure path, before exiting with the
    matching reserved code. A successful ``execvp`` writes nothing.
    """
    if status_fd is None:
        return
    try:
        os.write(status_fd, token.encode("ascii"))
    except OSError:
        # The parent already closed/abandoned the pipe — the reserved exit code
        # remains the fallback signal. Never let status reporting mask the error.
        pass


def parse_args(argv):
    """Parse ``--policy-json <json> -- <executable> [args...]``.

    Returns ``(policy_json, command)`` where ``command`` is a non-empty argv
    list. Raises ``LauncherArgsError`` on any structural problem.
    """
    if not argv or argv[0] != "--policy-json":
        raise LauncherArgsError("expected '--policy-json' as the first argument.")
    if len(argv) < 2:
        raise LauncherArgsError("missing value for '--policy-json'.")
    policy_json = argv[1]

    rest = argv[2:]
    if not rest or rest[0] != "--":
        raise LauncherArgsError("expected a literal '--' separator before the command.")
    command = rest[1:]
    if not command:
        raise LauncherArgsError("missing target command after '--'.")
    return policy_json, command


def parse_policy(policy_json):
    """Parse and validate the policy JSON into a ``{field: int | None}`` dict.

    Requires a top-level object whose keys are exactly ``POLICY_FIELDS`` and
    whose values are each ``None`` or a non-boolean integer >= 0. Raises
    ``LauncherPolicyError`` on any problem.
    """
    try:
        data = json.loads(policy_json)
    except (ValueError, TypeError) as error:
        raise LauncherPolicyError(f"policy is not valid JSON: {error}")

    if not isinstance(data, dict):
        raise LauncherPolicyError("policy must be a JSON object.")

    keys = set(data.keys())
    expected = set(POLICY_FIELDS)
    if keys != expected:
        missing = sorted(expected - keys)
        unknown = sorted(keys - expected)
        raise LauncherPolicyError(
            f"policy keys must be exactly {list(POLICY_FIELDS)}; "
            f"missing={missing}, unknown={unknown}."
        )

    policy = {}
    for field in POLICY_FIELDS:
        value = data[field]
        if value is None:
            policy[field] = None
            continue
        # ``bool`` is an ``int`` subclass; reject it explicitly. JSON ``true``/
        # ``false`` decode to Python bool.
        if isinstance(value, bool) or not isinstance(value, int):
            raise LauncherPolicyError(
                f"{field} must be null or a non-negative integer, got {type(value)!r}."
            )
        if value < 0:
            raise LauncherPolicyError(
                f"{field} must be null or a non-negative integer, got {value!r}."
            )
        policy[field] = value
    return policy


def _rlimit_const(name):
    """Return the ``resource.RLIMIT_*`` constant or fail closed if unavailable."""
    const = getattr(resource, name, None)
    if const is None:
        raise LauncherUnsupportedError(
            f"this kernel/build does not provide resource.{name}."
        )
    return const


def build_rlimit_settings(policy):
    """Build deterministic ``[(rlimit_const, soft, hard), ...]`` from a policy.

    Linux-only. Fails closed (``LauncherUnsupportedError``) when the ``resource``
    module is unavailable, when a deferred field is requested, or when a required
    ``RLIMIT_*`` constant is missing on this platform. Never silently skips a
    requested limit.

    Soft/hard choices:
    - ``core_size_bytes`` -> ``RLIMIT_CORE`` ``(v, v)`` (``0`` disables cores)
    - ``cpu_seconds``     -> ``RLIMIT_CPU``  ``(v, v + 1)`` so ``SIGXCPU`` (soft)
      is delivered before the hard ``SIGKILL``
    - ``file_size_bytes`` -> ``RLIMIT_FSIZE`` ``(v, v)``
    - ``open_files``      -> ``RLIMIT_NOFILE`` ``(v, v)``
    """
    if resource is None:
        raise LauncherUnsupportedError(
            "resource limits are unsupported on this platform (no 'resource' module)."
        )

    for field in _DEFERRED_FIELDS:
        if policy.get(field) is not None:
            raise LauncherUnsupportedError(
                f"{field} is not enforced in this stage; refusing to silently skip it."
            )

    settings = []

    core = policy.get("core_size_bytes")
    if core is not None:
        settings.append((_rlimit_const("RLIMIT_CORE"), core, core))

    cpu = policy.get("cpu_seconds")
    if cpu is not None:
        settings.append((_rlimit_const("RLIMIT_CPU"), cpu, cpu + 1))

    fsize = policy.get("file_size_bytes")
    if fsize is not None:
        settings.append((_rlimit_const("RLIMIT_FSIZE"), fsize, fsize))

    nofile = policy.get("open_files")
    if nofile is not None:
        settings.append((_rlimit_const("RLIMIT_NOFILE"), nofile, nofile))

    return settings


def apply_limits(settings):
    """Apply each ``(const, soft, hard)`` via ``resource.setrlimit``.

    Any failure raises ``OSError``/``ValueError`` to the caller (mapped to
    ``EXIT_APPLY_FAILED`` in ``main``). Failures are never caught and ignored.
    """
    for const, soft, hard in settings:
        resource.setrlimit(const, (soft, hard))


def main(argv):
    """Apply the validated policy, then ``execvp`` the target command.

    On success ``execvp`` replaces this process and never returns. Setup
    failures occur before ``execvp`` and return a reserved exit code, so the
    target never starts on a setup error. When an optional ``--status-fd`` is
    supplied, each launcher-owned failure also writes its matching ``STATUS_*``
    token to that pipe before returning, and a successful ``execvp`` closes the
    fd (close-on-exec) so the parent reads EOF with no payload.
    """
    # The status fd is extracted first so every later failure can report on it.
    # A malformed ``--status-fd`` cannot be trusted as a writable fd, so that
    # one failure is signalled by the reserved exit code alone.
    try:
        status_fd, rest = extract_status_fd(argv)
    except LauncherArgsError:
        return EXIT_BAD_ARGS

    try:
        policy_json, command = parse_args(rest)
    except LauncherArgsError:
        _emit_status(status_fd, STATUS_BAD_ARGS)
        return EXIT_BAD_ARGS

    try:
        policy = parse_policy(policy_json)
    except LauncherPolicyError:
        _emit_status(status_fd, STATUS_BAD_POLICY)
        return EXIT_BAD_POLICY

    try:
        settings = build_rlimit_settings(policy)
    except LauncherUnsupportedError:
        _emit_status(status_fd, STATUS_UNSUPPORTED)
        return EXIT_UNSUPPORTED

    try:
        apply_limits(settings)
    except Exception:
        _emit_status(status_fd, STATUS_APPLY_FAILED)
        return EXIT_APPLY_FAILED

    # Mark the status fd close-on-exec so a SUCCESSFUL execvp closes it
    # automatically (parent sees EOF, no payload) and the target never inherits
    # it. The fd stays open in THIS process, so the exec-failure path below can
    # still write its token. If we CANNOT make it close-on-exec we must fail
    # closed: the target could otherwise inherit the status fd and corrupt the
    # handshake, so we report a protocol error and never start the target.
    if status_fd is not None:
        try:
            os.set_inheritable(status_fd, False)
        except OSError:
            _emit_status(status_fd, STATUS_PROTOCOL_ERROR)
            return EXIT_EXEC_FAILED

    try:
        os.execvp(command[0], command)
    except OSError:
        _emit_status(status_fd, STATUS_EXEC_FAILED)
        return EXIT_EXEC_FAILED
    # execvp does not return on success; this is unreachable in practice.
    return EXIT_EXEC_FAILED  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
