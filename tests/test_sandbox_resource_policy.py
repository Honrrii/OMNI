"""Phase 11 Stage 9B-3A: sandbox resource-policy model tests.

Policy and validation only. These tests exercise the immutable, deterministic
``ResourceLimits`` shape and the platform-capability reporter. They apply NO
resource limits, spawn no process, and import no ``resource`` module. AST guards
prove the policy module itself stays free of subprocess/resource/preexec/os.exec
and shell execution.
"""

import ast
import dataclasses
import sys
from pathlib import Path

import pytest

from backend.app.sandbox.resource_policy import (
    ResourceLimits,
    resource_limits_supported,
)

FIELD_ORDER = (
    "cpu_seconds",
    "address_space_bytes",
    "file_size_bytes",
    "open_files",
    "process_count",
    "core_size_bytes",
)

POLICY_FILE = (
    Path(__file__).resolve().parent.parent
    / "backend"
    / "app"
    / "sandbox"
    / "resource_policy.py"
)


# ---------------------------------------------------------------------------
# 1-3. shape: fields, order, frozen, defaults
# ---------------------------------------------------------------------------
def test_exact_field_set_and_order():
    fields = tuple(f.name for f in dataclasses.fields(ResourceLimits))
    assert fields == FIELD_ORDER


def test_dataclass_is_frozen():
    limits = ResourceLimits()
    with pytest.raises(dataclasses.FrozenInstanceError):
        limits.cpu_seconds = 5  # type: ignore[misc]


def test_default_values():
    limits = ResourceLimits()
    assert limits.cpu_seconds is None
    assert limits.address_space_bytes is None
    assert limits.file_size_bytes is None
    assert limits.open_files is None
    assert limits.process_count is None
    # core_size_bytes defaults to 0 (desired "disable core dumps" policy).
    assert limits.core_size_bytes == 0


# ---------------------------------------------------------------------------
# 4-6. is_empty semantics
# ---------------------------------------------------------------------------
def test_default_policy_is_not_empty_because_core_size_is_zero():
    # core_size_bytes defaults to 0, not None, so the default is NOT empty.
    assert ResourceLimits().is_empty() is False


def test_all_none_policy_is_empty():
    limits = ResourceLimits(core_size_bytes=None)
    assert limits.is_empty() is True


def test_populated_policy_is_not_empty():
    assert ResourceLimits(core_size_bytes=None, cpu_seconds=1).is_empty() is False


# ---------------------------------------------------------------------------
# 7-10. validation
# ---------------------------------------------------------------------------
def test_zero_values_accepted_for_every_field():
    limits = ResourceLimits(**{name: 0 for name in FIELD_ORDER})
    for name in FIELD_ORDER:
        assert getattr(limits, name) == 0


def test_positive_values_accepted_for_every_field():
    limits = ResourceLimits(**{name: 7 for name in FIELD_ORDER})
    for name in FIELD_ORDER:
        assert getattr(limits, name) == 7


@pytest.mark.parametrize("name", FIELD_ORDER)
def test_negative_values_rejected_for_every_field(name):
    with pytest.raises(ValueError):
        ResourceLimits(**{name: -1})


@pytest.mark.parametrize("name", FIELD_ORDER)
def test_booleans_rejected_for_every_field(name):
    with pytest.raises(TypeError):
        ResourceLimits(**{name: True})


@pytest.mark.parametrize("name", FIELD_ORDER)
@pytest.mark.parametrize("bad", ["100", 1.5, 2.0, [1], {"a": 1}])
def test_non_integer_values_rejected_for_every_field(name, bad):
    with pytest.raises(TypeError):
        ResourceLimits(**{name: bad})


# ---------------------------------------------------------------------------
# 11-13. to_dict determinism / freshness / round-trip
# ---------------------------------------------------------------------------
def test_to_dict_key_order_and_values():
    limits = ResourceLimits(
        cpu_seconds=1,
        address_space_bytes=2,
        file_size_bytes=3,
        open_files=4,
        process_count=5,
        core_size_bytes=6,
    )
    out = limits.to_dict()
    assert list(out.keys()) == list(FIELD_ORDER)
    assert out == {
        "cpu_seconds": 1,
        "address_space_bytes": 2,
        "file_size_bytes": 3,
        "open_files": 4,
        "process_count": 5,
        "core_size_bytes": 6,
    }


def test_to_dict_is_deterministic():
    limits = ResourceLimits(cpu_seconds=10)
    assert limits.to_dict() == limits.to_dict()


def test_to_dict_returns_a_fresh_dict():
    limits = ResourceLimits(cpu_seconds=10)
    first = limits.to_dict()
    first["cpu_seconds"] = 999
    first["injected"] = True
    second = limits.to_dict()
    assert second["cpu_seconds"] == 10
    assert "injected" not in second


def test_dict_round_trip():
    for limits in (
        ResourceLimits(),
        ResourceLimits(core_size_bytes=None),
        ResourceLimits(
            cpu_seconds=1,
            address_space_bytes=2,
            file_size_bytes=3,
            open_files=4,
            process_count=5,
            core_size_bytes=6,
        ),
    ):
        assert ResourceLimits(**limits.to_dict()) == limits


# ---------------------------------------------------------------------------
# 14-15. platform capability reporting
# ---------------------------------------------------------------------------
def test_resource_limits_supported_returns_bool():
    assert isinstance(resource_limits_supported(), bool)


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="resource limit enforcement is Linux-only",
)
def test_resource_limits_supported_true_on_linux():
    assert resource_limits_supported() is True


# ---------------------------------------------------------------------------
# 16-17. AST guards: policy module stays pure
# ---------------------------------------------------------------------------
def _policy_tree():
    return ast.parse(POLICY_FILE.read_text(encoding="utf-8"), filename=str(POLICY_FILE))


def test_policy_module_imports_no_subprocess_or_resource():
    forbidden = {"subprocess", "resource"}
    offenders = []
    for node in ast.walk(_policy_tree()):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in forbidden:
                    offenders.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in forbidden:
                offenders.append(node.module)
    assert not offenders, f"resource_policy.py imports forbidden modules: {offenders}"


def test_policy_module_has_no_preexec_or_exec_or_shell():
    tree = _policy_tree()

    # No preexec_fn keyword anywhere.
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword):
            assert node.arg != "preexec_fn", "resource_policy.py uses preexec_fn"
        # No shell=True.
        if (
            isinstance(node, ast.keyword)
            and node.arg == "shell"
            and isinstance(node.value, ast.Constant)
            and node.value.value is True
        ):
            raise AssertionError("resource_policy.py uses shell=True")

    # No os.exec* / os.system / os.popen / subprocess.* calls.
    banned_attrs = {"system", "popen"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            value = node.func.value
            if attr.startswith("exec"):
                raise AssertionError(f"resource_policy.py calls os.{attr}")
            if attr in banned_attrs:
                raise AssertionError(f"resource_policy.py calls a banned {attr}()")
            if isinstance(value, ast.Name) and value.id == "subprocess":
                raise AssertionError("resource_policy.py calls subprocess")
