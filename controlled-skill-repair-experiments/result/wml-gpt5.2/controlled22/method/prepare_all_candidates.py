#!/usr/bin/env python3
"""Prepare the 22 repaired WML candidates for native task evaluation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(os.environ.get("WML_CONTROLLED_ROOT", Path(__file__).resolve().parent.parent))
CANDIDATES = ROOT / "candidates"
PREPARED = ROOT / "prepared"
PACKAGE = Path(
    "/Users/king/Downloads/03_论文科研/skill-repair-controlled-datasets-20261020"
)
RUNNER = PACKAGE / "tools" / "runner.py"


def main() -> int:
    candidates = sorted(path for path in CANDIDATES.iterdir() if path.is_dir())
    if len(candidates) != 22:
        raise RuntimeError(f"expected 22 candidates, got {len(candidates)}")
    PREPARED.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for index, candidate in enumerate(candidates, 1):
        destination = PREPARED / candidate.name
        if (destination / "RUN.json").is_file() and (
            destination / "PREPARED_SHA256.json"
        ).is_file():
            print(f"SKIP {index:02d}/22 {candidate.name}", flush=True)
        else:
            if destination.exists():
                raise RuntimeError(f"incomplete prepared directory exists: {destination}")
            subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "prepare-eval",
                    "--trial",
                    candidate.name,
                    "--candidate",
                    str(candidate),
                    "--out",
                    str(destination),
                ],
                check=True,
            )
            print(f"READY {index:02d}/22 {candidate.name}", flush=True)
        rows.append({"trial_id": candidate.name, "prepared": str(destination)})
    (ROOT / "prepared_manifest.json").write_text(
        json.dumps({"total": 22, "trials": rows}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
