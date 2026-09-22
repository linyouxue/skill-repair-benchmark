# Materialize required deliverables and verify before finishing

Use this when the evaluator expects specific output files (e.g., a processed video and a JSON report) and a run could otherwise end with an empty output inventory.

## Trigger

Apply this gate when you can name the expected output filenames/paths up front; treat it as a **hard termination precondition** (no PASS → no `end_turn`). Skip when the caller explicitly wants only console/stdout output.

## Procedure

1. **Inventory deliverables** from the task spec (paths + formats), and treat them as *blocking*.
2. **Produce artifacts** by running the minimal pipeline that writes those files.
3. **Verify artifacts** exist, are non-empty, and are readable.
4. **On failure**: fix the smallest upstream cause and repeat verification; do not end the run until all deliverables pass.

## Runnable verification snippet (Python)

```python
from __future__ import annotations

import json
from pathlib import Path


def verify_file(path: str) -> tuple[bool, str]:
    p = Path(path)
    if not p.exists():
        return False, f"missing: {p}"
    if p.stat().st_size == 0:
        return False, f"empty file: {p}"
    return True, f"ok: {p} ({p.stat().st_size} bytes)"


def verify_json_schema(path: str, required_keys: set[str]) -> tuple[bool, str]:
    ok, msg = verify_file(path)
    if not ok:
        return False, msg
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"json parse failed: {path}: {e}"

    missing = required_keys - set(data)
    if missing:
        return False, f"missing keys: {path}: {sorted(missing)}"
    return True, f"ok: {path} keys present"


def gate(required: dict[str, str], required_report_keys: set[str]) -> None:
    results: list[tuple[str, bool, str]] = []

    # Branch A: both video and report required
    if "video" in required and "report" in required:
        ok_v, msg_v = verify_file(required["video"])
        ok_r, msg_r = verify_json_schema(required["report"], required_report_keys)
        results.extend([
            ("video", ok_v, msg_v),
            ("report", ok_r, msg_r),
        ])

    # Branch B: only a report required
    elif "report" in required:
        ok_r, msg_r = verify_json_schema(required["report"], required_report_keys)
        results.append(("report", ok_r, msg_r))
    else:
        raise ValueError("no deliverables configured")

    failures = [(k, m) for (k, ok, m) in results if not ok]
    for k, ok, m in results:
        print(f"{k}: {'PASS' if ok else 'FAIL'} | {m}")

    # Verification step (prescribe next action on failure)
    if failures:
        failed_kinds = [k for k, _ in failures]
        raise SystemExit(
            "Deliverables gate failed for: "
            + ", ".join(failed_kinds)
            + ". Next action: run the pipeline step that WRITES the failing deliverable(s) "
            + "(fix output path/filename first; regenerate malformed JSON if needed), then re-run this gate."
        )


required = {
    "video": "output_video.mp4",
    "report": "report.json",
}

gate(required, {
    "original_duration_seconds",
    "compressed_duration_seconds",
    "removed_duration_seconds",
    "compression_percentage",
    "segments_removed",
})
```

## Minimal corrective actions (runtime branches)

- If the **video is missing/empty**: rerun the video-writing render/encode step with the correct output path (do not stop after producing segment JSON).
- If the **report is missing/empty**: rerun the report generator with the correct `--output` path.
- If the **report JSON does not parse**: open and fix the writing code to emit valid JSON (no trailing commas; serialize numbers as numbers), regenerate, then re-run the gate.
- If the **report schema is missing keys**: adjust report generation to populate required keys (or update the deliverables inventory to match the requested schema), regenerate, then re-run the gate.

## Termination precondition template

Before finishing, record the gate results in your final response, e.g.:

- `output_video.mp4`: PASS (exists, non-empty)
- `report.json`: PASS (exists, non-empty, JSON parses, required keys present)
