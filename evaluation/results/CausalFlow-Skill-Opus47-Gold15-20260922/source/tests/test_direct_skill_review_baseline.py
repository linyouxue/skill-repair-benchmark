from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_direct_review_cli_imports_workspace_package_outside_repo(tmp_path: Path):
    workspace = Path(__file__).resolve().parents[1]
    script = workspace / "repro_wrappers" / "defects" / "run_direct_skill_review_baseline.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--defective-bundle" in completed.stdout
