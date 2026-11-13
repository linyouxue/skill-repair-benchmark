---
name: report-generator
description: Generate the required `compression_report.json` with measured durations
  (via ffprobe) and the final segment list.
---

## Steps
1. Generate the report from the original video, the processed video, and the **final merged segments** file:
   ```bash
   python3 /root/.claude/skills/report-generator/scripts/generate_report.py \
     --original data/input_video.mp4 \
     --compressed /root/compressed_video.mp4 \
     --segments /root/all_segments.json \
     --output /root/compression_report.json
   ```
2. Verify the JSON has the required keys and consistent math:
   - `original_duration_seconds ≈ compressed_duration_seconds + removed_duration_seconds`
   - `compression_percentage ≈ removed / original * 100`

## Expected Result
A valid `compression_report.json` matching the task schema, with durations derived from ffprobe and `segments_removed` matching the actual removals.
