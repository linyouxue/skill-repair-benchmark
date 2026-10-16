---
name: video-processor
description: Process videos by removing segments and concatenating remaining parts.
---

# Video Segment Processor

Processes videos by removing specified segments and concatenating the remaining parts.

## End-to-end workflow + completion gate

1. Write down the required deliverables (typically: processed video + JSON report) and the intermediate artifacts needed to produce them.
2. Resolve the evaluator-visible workspace root (where outputs must land) and either `cd` into it or set **absolute** output paths under it for every stage.
3. Execute the pipeline in order: extract audio → compute energy → detect removal segments → merge/normalize segments → process video → generate report.
4. Treat any intermediate JSON (energies, detected segments) as inputs to later steps, not as deliverables.
5. Before stopping, run a completion gate: verify the deliverables exist **in the workspace** and are internally consistent.

```python
from pathlib import Path
import json

workspace = Path(workspace_root)
video_out = workspace / Path(video_output_path).name
report_out = workspace / Path(report_output_path).name

assert workspace.exists(), "workspace root missing"
assert video_out.exists(), "missing processed video in workspace"
assert report_out.exists(), "missing JSON report in workspace"

report = json.loads(report_out.read_text())
required = {"original_duration_seconds", "compressed_duration_seconds", "removed_duration_seconds"}
assert required.issubset(report), "report missing required fields"
```

Decision rule: if outputs were produced outside the workspace, move/copy them into the workspace using the expected filenames, then re-run the completion gate checks against the workspace paths.

Read references/completion-gate.md when the task requires final deliverables and intermediate artifacts are easy to confuse with outputs. Skip when the caller only requested an intermediate artifact (e.g., energies.json) and no final files are required.

## Remove segments and render output video

Use the segment-removal operation to cut out unwanted intervals and concatenate the remainder.

```bash
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input /path/to/input.mp4 \
    --output /path/to/output.mp4 \
    --remove-segments /path/to/segments.json
```

Decision rule: prefer a single “all segments” JSON if you have already merged overlaps/gaps; otherwise pass multiple detector outputs and validate the combined result.

## Common pitfalls

- Stopping after generating intermediate artifacts (audio/energy/segments) without producing the required deliverables.
- Assuming success without checking that the output files were written to the evaluator-visible workspace root.
- Reporting duration math without validating it against the produced video and report.
