# Run → verify output artifact (hard-stop loop)

Use this procedure whenever you must produce a concrete deliverable (typically a JSON file) from code.

## Goal

Prevent “silent failures” where the agent edits code, but never re-runs successfully and never opens the output artifact.

## Procedure (with runtime branches)

```python
import json
import os
import subprocess
import sys
from typing import Iterable


def run_cmd(argv: list[str]) -> None:
    p = subprocess.run(argv, capture_output=True, text=True)

    # Branch A: runtime failure (syntax error, exception, missing file, etc.)
    if p.returncode != 0:
        print("STDOUT:\n", p.stdout)
        print("STDERR:\n", p.stderr)
        raise SystemExit(
            "Run failed (non-zero exit). Fix the runtime error before reasoning about outputs."
        )


def verify_json_artifact(path: str, required_keys: Iterable[str]) -> dict:
    # Branch B: program ran but did not write the artifact
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Missing output artifact: {path}. Re-check write path and run again."
        )

    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    missing = [k for k in required_keys if k not in obj]
    # Branch C: artifact exists but schema is wrong/stale
    if missing:
        raise ValueError(
            f"Output JSON missing keys {missing}. Update emitter/schema and re-run end-to-end."
        )

    return obj


def main() -> None:
    # Replace with the task's real command and required keys.
    run_cmd([sys.executable, "-m", "your_module"])
    report = verify_json_artifact("/path/to/output.json", required_keys=["k1", "k2"])
    print("Verified keys:", sorted(report.keys()))


if __name__ == "__main__":
    main()
```

## Verification and corrective action

- If the run fails (Branch A):
  1. Fix syntax/traceback first.
  2. Re-run the same command until it exits successfully.

- If the artifact is missing (Branch B):
  1. Confirm the writer code is reached (e.g., add a log line right before writing).
  2. Confirm the output directory exists and the path matches the required one.
  3. Re-run end-to-end.

- If required keys are missing (Branch C):
  1. Update the JSON emitter to include the required fields.
  2. Re-run end-to-end and re-open the artifact.
