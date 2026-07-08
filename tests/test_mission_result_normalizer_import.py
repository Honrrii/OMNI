"""Phase 10 Stage 2C guard: the normalizer helper stays lightweight.

backend.app.omni_core.mission_result_normalizer was extracted from
backend.app.main so that tests (and other callers) can normalize mission
results without importing FastAPI routes, ML routes, torch, torchvision, and
python-multipart.

This test imports the helper in a fresh subprocess and asserts that doing so
does NOT load backend.app.main. A subprocess keeps the check robust and free
of import-order coupling with the rest of the test session.
"""

import subprocess
import sys


def test_helper_import_does_not_load_main():
    code = (
        "import sys\n"
        "from backend.app.omni_core.mission_result_normalizer import "
        "normalize_mission_result\n"
        "print('backend.app.main' in sys.modules)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"subprocess failed:\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )
    assert proc.stdout.strip() == "False", (
        f"importing the helper loaded backend.app.main; stdout={proc.stdout!r}"
    )
