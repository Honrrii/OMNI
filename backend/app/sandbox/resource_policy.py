"""
OMNI Sandbox — resource-limit policy model (Phase 11 Stage 9B-3A).

This stage defines POLICY ONLY. It is an immutable, deterministic description of
the OS resource limits OMNI may eventually apply to a sandboxed command. NOTHING
is enforced here: this module applies no limits, spawns no process, imports no
``resource`` module, and touches no execution path.

Enforcement is deliberately deferred. Linux-only application of these limits
(via a dedicated single-threaded child launcher, not ``preexec_fn``) is planned
for Stage 9B-3B; termination classification and report mapping for Stage 9B-3C.

HONEST SECURITY NOTE — this is NOT a full security sandbox, and a resource-limit
policy does not make it one. Resource limits (once enforced) bound CPU, memory,
file size, and similar quotas, but provide no filesystem jail, no network
isolation, no seccomp/cgroups/container isolation, and no protection from
untrusted code. See ``execution.py`` for the broader honest limitations.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional

# Fixed field order shared by ``to_dict`` and the dataclass definition, so the
# serialized policy is deterministic and stable.
_FIELD_ORDER = (
    "cpu_seconds",
    "address_space_bytes",
    "file_size_bytes",
    "open_files",
    "process_count",
    "core_size_bytes",
)


@dataclass(frozen=True)
class ResourceLimits:
    """An immutable, validated description of desired OS resource limits.

    Every field is an optional non-negative integer. ``None`` means "do not set
    this limit" (inherit the ambient value); a concrete integer is the desired
    soft/hard value a future enforcement stage would apply. ``0`` is accepted
    everywhere and is meaningful for ``core_size_bytes`` (disable core dumps).

    Fields map to the eventual ``RLIMIT_*`` constants:

    - ``cpu_seconds``          -> ``RLIMIT_CPU``
    - ``address_space_bytes``  -> ``RLIMIT_AS``
    - ``file_size_bytes``      -> ``RLIMIT_FSIZE``
    - ``open_files``           -> ``RLIMIT_NOFILE``
    - ``process_count``        -> ``RLIMIT_NPROC`` (see note)
    - ``core_size_bytes``      -> ``RLIMIT_CORE``

    Notes:
    - ``process_count`` represents a future ``RLIMIT_NPROC``. It is considered
      risky (per-UID, counts existing processes, can wedge the parent) and will
      NOT be enforced in Stage 9B-3A — it is policy metadata only here.
    - ``core_size_bytes`` defaults to ``0`` to express the desired future policy
      of disabling core dumps, but nothing is applied in this stage. Because of
      this default, a default ``ResourceLimits()`` is intentionally NOT empty.
    """

    cpu_seconds: Optional[int] = None
    address_space_bytes: Optional[int] = None
    file_size_bytes: Optional[int] = None
    open_files: Optional[int] = None
    process_count: Optional[int] = None
    core_size_bytes: Optional[int] = 0

    def __post_init__(self) -> None:
        for name in _FIELD_ORDER:
            value = getattr(self, name)
            if value is None:
                continue
            # ``bool`` is an ``int`` subclass; reject it explicitly so flags are
            # never silently treated as 0/1 limits.
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(
                    f"{name} must be None or a non-negative integer, "
                    f"got {type(value)!r}."
                )
            if value < 0:
                raise ValueError(
                    f"{name} must be None or a non-negative integer, got {value!r}."
                )

    def is_empty(self) -> bool:
        """True only when every field is ``None``.

        Because ``core_size_bytes`` defaults to ``0`` (not ``None``), the default
        ``ResourceLimits()`` is NOT empty; an all-``None`` policy is.
        """
        return all(getattr(self, name) is None for name in _FIELD_ORDER)

    def to_dict(self) -> dict[str, Optional[int]]:
        """Return a fresh dict in the fixed field order (deterministic)."""
        return {name: getattr(self, name) for name in _FIELD_ORDER}


def resource_limits_supported() -> bool:
    """Report whether this platform can enforce resource limits (Linux only).

    Capability reporting only — this applies nothing. Enforcement lands in a
    later, Linux-only stage; non-Linux platforms (native Windows has no
    ``resource`` module; macOS ignores ``RLIMIT_AS``) are out of scope.
    """
    return sys.platform.startswith("linux")
