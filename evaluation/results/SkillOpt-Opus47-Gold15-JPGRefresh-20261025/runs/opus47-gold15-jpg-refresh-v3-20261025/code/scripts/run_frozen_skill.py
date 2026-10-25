#!/usr/bin/env python3
"""Execute one already-frozen Skill bundle without another optimizer pass."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.common.executor_api import run_method_skill  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--method", default="skillopt")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--skill-bundle", type=Path, required=True)
    parser.add_argument("--stage", default="final-frozen")
    args = parser.parse_args()

    result = run_method_skill(
        task_id=args.task,
        method_id=args.method,
        run_id=args.run_id,
        skill_bundle=args.skill_bundle.resolve(),
        stage=args.stage,
        persist_method_result=True,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
