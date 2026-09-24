# Deliverable commit phase (never exit without the required artifact)

## When to use

Use this procedure when the task is graded on the presence and schema-validity of a required file (commonly `report.json`), or when upstream optimization/IO may fail and you still must return a structured artifact.

## Procedure

1. **Decide the required deliverable set** (names + schema) from the task statement.
2. **Build the payload in memory** with strict types (convert NumPy scalars to Python scalars).
3. **Runtime branch:** write a normal payload on success; otherwise write an `error` payload.
4. **Write atomically** (tmp file then rename) to avoid partial files.
5. **Verification:** immediately re-open and parse to confirm the artifact exists and is valid; on failure, rewrite using a simpler payload and re-verify.

## Runnable Python template

```python
from __future__ import annotations

import json
import os
import tempfile
import traceback
from typing import Any, Dict


def _jsonable(x: Any) -> Any:
    try:
        import numpy as np
        if isinstance(x, (np.integer, np.floating)):
            return x.item()
    except Exception:
        pass
    return x


def commit_report(path: str, payload: Dict[str, Any]) -> None:
    payload = {k: _jsonable(v) for k, v in payload.items()}

    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)

    fd, tmp = tempfile.mkstemp(prefix=".tmp_report_", suffix=".json", dir=d)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def finalize_report(report_path: str, *, compute_fn) -> None:
    try:
        result = compute_fn()
        payload = {"status": "ok", "result": result}
    except Exception as e:
        payload = {
            "status": "error",
            "error": {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc(limit=20),
            },
        }

    commit_report(report_path, payload)

    # Verification step
    try:
        with open(report_path) as f:
            json.load(f)
    except Exception as e:
        commit_report(
            report_path,
            {
                "status": "error",
                "error": {
                    "type": type(e).__name__,
                    "message": f"report verification failed: {e}",
                },
            },
        )
        with open(report_path) as f:
            json.load(f)


if __name__ == "__main__":
    finalize_report("report.json", compute_fn=lambda: {"metric": 1.0})
    print("wrote and verified report.json")
```

## Verification checklist

- Confirm the file exists: `os.path.exists(report_path)`.
- Confirm it is valid JSON: `json.load(open(report_path))`.
- If verification fails: **rewrite** a minimal payload and re-verify before exiting.
