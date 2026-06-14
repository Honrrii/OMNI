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
    target never starts on a setup error.
    """
    try:
        policy_json, command = parse_args(argv)
    except LauncherArgsError:
        return EXIT_BAD_ARGS

    try:
        policy = parse_policy(policy_json)
    except LauncherPolicyError:
        return EXIT_BAD_POLICY

    try:
        settings = build_rlimit_settings(policy)
    except LauncherUnsupportedError:
        return EXIT_UNSUPPORTED

    try:
        apply_limits(settings)
    except Exception:
        return EXIT_APPLY_FAILED

    try:
        os.execvp(command[0], command)
    except OSError:
        return EXIT_EXEC_FAILED
    # execvp does not return on success; this is unreachable in practice.
    return EXIT_EXEC_FAILED  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
