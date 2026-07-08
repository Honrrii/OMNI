"""Symbolic equation sanity sandbox check (Phase 11 Stage 2).

Validate a tiny algebraic relationship (left == right) by evaluating both sides
with a safe, AST-based arithmetic evaluator. No ``eval``, no ``exec``, no sympy,
no external binaries, no I/O. Only numbers, named variables, the operators
``+ - * / **`` (and unary +/-), and parentheses are permitted.

Expected input shape::

    {
        "equation_id": "ohms_law",
        "left": "V",
        "right": "I * R",
        "values": {"V": 12, "I": 3, "R": 4},
        "tolerance": 0.000001,
    }

Outcomes:
- both sides equal within tolerance -> status "passed"
- mismatch                          -> status "completed", one "warning" check
- missing/invalid/unsafe input      -> status "skipped", one "info" check
"""
from __future__ import annotations

import ast
from typing import Any, Optional

from backend.app.sandbox.report import SandboxCheckResult, SandboxReport

_SANDBOX_NAME = "equation_sanity"
_CHECK_ID = "equation.sanity"
_DEFAULT_TOLERANCE = 1e-6

# Binary operators permitted in the safe evaluator.
_BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_UNARY_OPS = (ast.UAdd, ast.USub)


class _UnsafeExpression(Exception):
    """Raised when an expression contains a disallowed node or unknown name."""


def _safe_eval(expr: str, values: dict[str, float]) -> float:
    """Evaluate a simple arithmetic expression deterministically and safely.

    Raises _UnsafeExpression for anything outside the permitted grammar (calls,
    attributes, comprehensions, unknown names, etc.) or for division by zero.
    """
    if not isinstance(expr, str) or not expr.strip():
        raise _UnsafeExpression("empty expression")

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as error:
        raise _UnsafeExpression(f"syntax error: {error}") from error

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, _BIN_OPS):
                raise _UnsafeExpression("disallowed binary operator")
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise _UnsafeExpression("division by zero")
                return left / right
            # ast.Pow
            return left ** right
        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, _UNARY_OPS):
                raise _UnsafeExpression("disallowed unary operator")
            operand = _eval(node.operand)
            return +operand if isinstance(node.op, ast.UAdd) else -operand
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise _UnsafeExpression("non-numeric constant")
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id not in values:
                raise _UnsafeExpression(f"unknown variable '{node.id}'")
            return values[node.id]
        raise _UnsafeExpression(f"disallowed expression node: {type(node).__name__}")

    return _eval(tree)


def _coerce_values(raw: Any) -> Optional[dict[str, float]]:
    if not isinstance(raw, dict):
        return None
    cleaned: dict[str, float] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        cleaned[key] = float(value)
    return cleaned


def _skip(message: str) -> SandboxReport:
    return SandboxReport(
        sandbox=_SANDBOX_NAME,
        status="skipped",
        checks=[
            SandboxCheckResult(
                check_id="equation_sanity.input",
                ok=True,
                severity="info",
                message=message,
                metadata={"reason": "missing_or_invalid_input"},
            )
        ],
    )


def _format_number(value: float) -> str:
    """Stable numeric string: integers render without a trailing .0."""
    rounded = round(float(value), 6)
    if rounded == int(rounded):
        return str(int(rounded))
    return repr(rounded)


def run_equation_sanity_check(inputs: Optional[dict[str, Any]]) -> SandboxReport:
    """Run the deterministic equation sanity check over ``inputs``."""
    if not isinstance(inputs, dict):
        return _skip("equation_sanity requires a dict of inputs; none was provided.")

    left = inputs.get("left")
    right = inputs.get("right")
    if not isinstance(left, str) or not left.strip():
        return _skip("equation_sanity requires a non-empty 'left' expression string.")
    if not isinstance(right, str) or not right.strip():
        return _skip("equation_sanity requires a non-empty 'right' expression string.")

    values = _coerce_values(inputs.get("values"))
    if values is None:
        return _skip(
            "equation_sanity requires a 'values' dict mapping variable names to numbers."
        )

    tolerance = inputs.get("tolerance")
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
        tolerance = _DEFAULT_TOLERANCE
    tolerance = abs(float(tolerance))

    equation_id = inputs.get("equation_id")
    equation_id = equation_id if isinstance(equation_id, str) and equation_id.strip() else "equation"

    try:
        left_value = _safe_eval(left, values)
        right_value = _safe_eval(right, values)
    except _UnsafeExpression as error:
        return _skip(
            f"equation_sanity could not evaluate the expression safely: {error}."
        )

    delta = abs(left_value - right_value)
    metadata = {
        "equation_id": equation_id,
        "left": left,
        "right": right,
        "left_value": round(left_value, 6),
        "right_value": round(right_value, 6),
        "delta": round(delta, 6),
        "tolerance": round(tolerance, 6),
    }

    if delta <= tolerance:
        check = SandboxCheckResult(
            check_id=_CHECK_ID,
            ok=True,
            severity="info",
            message=f"Equation '{equation_id}' holds within tolerance.",
            expected=_format_number(left_value),
            actual=_format_number(right_value),
            metadata=metadata,
        )
        return SandboxReport(
            sandbox=_SANDBOX_NAME,
            status="passed",
            checks=[check],
        )

    check = SandboxCheckResult(
        check_id=_CHECK_ID,
        ok=False,
        severity="warning",
        message=(
            f"Equation '{equation_id}' does not hold: "
            f"left={_format_number(left_value)} vs right={_format_number(right_value)}."
        ),
        expected=_format_number(left_value),
        actual=_format_number(right_value),
        metadata=metadata,
    )
    return SandboxReport(
        sandbox=_SANDBOX_NAME,
        status="completed",
        checks=[check],
    )
