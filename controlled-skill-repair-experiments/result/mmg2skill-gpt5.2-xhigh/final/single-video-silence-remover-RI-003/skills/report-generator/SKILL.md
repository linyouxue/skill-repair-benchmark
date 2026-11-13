---
name: report-generator
description: Generate the required task-format `compression_report.json` from the
  original video, the compressed video, and the final removal segment list.
---

## Steps
1. Ensure you already have:
   - the original video (`input_video.mp4`)
   - the compressed video (`compressed_video.mp4`)
   - the finalized removal segments file with a top-level `segments` array (e.g., `all_segments.json`)
2. Run the bundled report generator from the workspace:
   ```bash
   python3 report-generator/scripts/generate_report.py \
     --original /path/to/original.mp4 \
     --compressed /path/to/compressed.mp4 \
     --segments /path/to/all_segments.json \
     --output /path/to/compression_report.json
   ```
3. Validate the JSON keys match the required schema:
   `original_duration_seconds`, `compressed_duration_seconds`, `removed_duration_seconds`, `compression_percentage`, `segments_removed`.

## Expected Result
A `compression_report.json` whose durations come from ffprobe and whose `segments_removed` equals the `segments` list from the provided segments file.
