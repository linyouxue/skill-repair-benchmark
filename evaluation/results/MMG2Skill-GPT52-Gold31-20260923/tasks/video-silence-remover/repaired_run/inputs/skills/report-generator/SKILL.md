---
name: report-generator
description: Create `compression_report.json` with consistent duration math and a
  `segments_removed` list matching the required schema.
---

## Steps
1. Generate a report from the original, compressed video, and the removal segments:
   ```bash
   python3 /root/.claude/skills/report-generator/scripts/generate_report.py \
     --original data/input_video.mp4 \
     --compressed compressed_video.mp4 \
     --segments all_segments.json \
     --output compression_report.json
   ```
2. Validate the report file exists and conforms to the required keys (`original_duration_seconds`, `compressed_duration_seconds`, `removed_duration_seconds`, `compression_percentage`, `segments_removed`):
   - `ls -l compression_report.json`
   - `cat compression_report.json`
3. If the generator includes extra keys inside `segments_removed` items (e.g., `"type"`), rewrite the file to the exact required item schema (`start`, `end`, `duration`) while keeping the top-level duration fields:
   ```bash
   python3 - <<'PY'
   import json
   p="compression_report.json"
   d=json.load(open(p))
   d["segments_removed"]=[{"start":s["start"],"end":s["end"],"duration":s["duration"]} for s in d.get("segments_removed",[])]
   json.dump(d, open(p,"w"), indent=2)
   PY
   ```
4. Ensure duration math is consistent (within small rounding error): `original ≈ compressed + removed`.
## Expected Result
`compression_report.json` exists in the current workspace, matches the requested structure, and its duration values are internally consistent.
