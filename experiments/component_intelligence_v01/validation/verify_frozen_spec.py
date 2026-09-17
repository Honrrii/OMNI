"""Read-only, standalone verification of the human-frozen semantic authority."""
from __future__ import annotations

import hashlib
from pathlib import Path

EXPECTED_SHA256 = "8c7f5a5f61feb2288229925323c63664c0a4ee756886068d46b87877cd947115"
SPEC_PATH = Path(__file__).resolve().parent.parent / "frozen_testcube_spec.md"


def observed_sha256() -> str:
    return hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()


def main() -> int:
    try:
        observed = observed_sha256()
    except OSError:
        print("FAIL frozen-spec unreadable")
        return 1
    if observed != EXPECTED_SHA256:
        print(f"FAIL frozen-spec sha256={observed} expected={EXPECTED_SHA256}")
        return 1
    print(f"PASS frozen-spec sha256={observed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
