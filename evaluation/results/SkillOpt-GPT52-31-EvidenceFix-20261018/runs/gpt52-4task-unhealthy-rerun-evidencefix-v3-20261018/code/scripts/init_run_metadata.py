#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.common.paths import load_task_ids  # noqa: E402


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"run-{datetime.now(UTC):%Y%m%dT%H%M%SZ}")
    args = parser.parse_args()

    metadata = {
        "run_id": args.run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "root": str(ROOT),
        "sources": load_json(ROOT / "configs" / "source_versions.json"),
        "task_list": load_task_ids(),
        "model": {
            "route": os.environ.get("BENCHMARK_MODEL", ""),
            "reasoning_effort": os.environ.get("BENCHMARK_REASONING_EFFORT", ""),
        },
        "budget": {
            "rounds": 1,
            "candidates_per_task": 1,
            "run_no_skill": False,
            "run_original_skill": True,
        },
        "conditions": {
            "baseline": "original-skill",
            "method": "method-skill",
        },
    }
    out = ROOT / "experiments" / args.run_id / "metadata.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
