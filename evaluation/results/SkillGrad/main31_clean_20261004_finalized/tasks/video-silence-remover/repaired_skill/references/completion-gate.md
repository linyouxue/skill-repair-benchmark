# Completion gate for deliverables (video + report)

Use this when the task requires final deliverables and you have produced intermediate artifacts (audio, energies, segment JSONs) but have not yet verified the final outputs.

## Procedure

1. Identify the deliverables and their expected paths.
2. Verify that both files exist and are non-empty.
3. Verify the processed video is readable and has a plausible duration.
4. Verify the JSON report has required fields and consistent duration math.
5. If any check fails: go back to the missing stage (video processing or report generation) and re-run it, then re-check.

```python
from pathlib import Path
import json
import subprocess

# Inputs (fill in at runtime)
video_output_path = "..."
report_output_path = "..."

video_out = Path(video_output_path)
report_out = Path(report_output_path)

# Branch A: missing outputs
missing = [p for p in (video_out, report_out) if not p.exists() or p.stat().st_size == 0]
if missing:
    raise FileNotFoundError(f"Missing deliverables: {missing}. Re-run video processing and/or report generation.")

# Probe duration via ffprobe
cmd = [
    "ffprobe", "-v", "error", "-show_entries", "format=duration",
    "-of", "default=noprint_wrappers=1:nokey=1", str(video_out)
]
compressed_seconds = float(subprocess.check_output(cmd, text=True).strip())

report = json.loads(report_out.read_text())

# Branch B: schema/math problems
required = {"original_duration_seconds", "compressed_duration_seconds", "removed_duration_seconds"}
if not required.issubset(report):
    raise ValueError(f"Report missing fields {required - set(report)}. Re-run report generator with correct inputs.")

orig = float(report["original_duration_seconds"])
comp = float(report["compressed_duration_seconds"])
rem = float(report["removed_duration_seconds"])

# Verification: duration sanity + internal consistency
# (Use a tolerant check because ffprobe and segment math can differ slightly.)
tol = max(1.0, 0.01 * orig)
if abs(comp - compressed_seconds) > tol:
    raise AssertionError(
        f"Report/video duration mismatch: report={comp:.3f}s ffprobe={compressed_seconds:.3f}s. "
        "Recompute compressed duration from the produced file and regenerate the report."
    )
if abs((comp + rem) - orig) > tol:
    raise AssertionError(
        f"Duration math inconsistent: compressed+removed != original within tol={tol:.3f}. "
        "Re-check merged segments (overlaps/double-counting) and regenerate report."
    )

print("Completion gate passed: outputs exist and durations are consistent.")
```

## Notes

- If the report math fails, the most common cause is overlapping removal segments that were double-counted; fix by normalizing/merging segments before video processing and report generation.
- If ffprobe cannot read the output, re-run the render step and inspect ffmpeg stderr for codec/container errors.
