# Write and verify a required JSON deliverable (hard gate)

Use this procedure when the evaluator expects a specific on-disk JSON file (exact path + filename). Treat it as a non-negotiable finalization step: analysis is not graded if the artifact is missing.

## Algorithm

1. Determine the **exact** required output path from the task statement (directory + filename).
2. Materialize a payload object that matches the required schema.
3. Create parent directories.
4. Write JSON atomically (write temp file → fsync/flush → rename).
5. Read the file back and `json.loads` it.
6. Verify it is non-empty and has required top-level keys.

## Runnable Python (with branches)

```python
import json
import os
from pathlib import Path
from typing import Any


def write_required_json(out_path: Path, payload: Any) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")

    # Branch A: payload is not JSON-serializable -> fail fast with a helpful message
    try:
        text = json.dumps(payload, indent=2, sort_keys=True)
    except TypeError as e:
        raise TypeError(
            f"Payload is not JSON-serializable: {e}. "
            "Convert non-primitive objects (e.g., Path, set) to strings/lists first."
        )

    # Branch B: normal write path (atomic rename)
    with tmp_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())

    tmp_path.replace(out_path)


def verify_required_json(out_path: Path, required_keys: set[str] | None = None) -> dict:
    out_path = Path(out_path)

    # Branch C: file missing/empty -> instruct next action
    if not out_path.exists():
        raise FileNotFoundError(
            f"Missing required deliverable: {out_path}. "
            "Next: run write_required_json() with the exact harness path."
        )
    if out_path.stat().st_size == 0:
        raise ValueError(
            f"Deliverable is empty: {out_path}. "
            "Next: re-write JSON and ensure the file is closed/flushed before verification."
        )

    text = out_path.read_text(encoding="utf-8")

    # Branch D: invalid JSON -> instruct next action
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Deliverable is not valid JSON ({e}): {out_path}. "
            "Next: re-write using json.dumps(...) and avoid trailing non-JSON text."
        )

    if required_keys:
        missing = [k for k in required_keys if k not in obj]
        if missing:
            raise KeyError(
                f"Deliverable missing required keys {missing}: {out_path}. "
                "Next: update the payload schema and re-write the file."
            )

    return obj


# Example usage (replace required_keys with the task's schema keys)
if __name__ == "__main__":
    out_path = Path("/app/output") / "report.json"
    payload = {"status": "ok", "details": {}}

    write_required_json(out_path, payload)
    verify_required_json(out_path, required_keys={"status", "details"})
    print("deliverable ok")
```

## Verification step (must be done right before ending the run)

- Run `verify_required_json(...)` and ensure it returns an object.
- On failure:
  - `FileNotFoundError`/empty file → re-run `write_required_json(...)` with the **exact** required path.
  - `JSONDecodeError` → re-serialize with `json.dumps(...)` only; remove any non-JSON suffix/prefix.
  - `KeyError` → fix payload schema, then re-write and re-verify.

Only after verification passes should you end the run.
