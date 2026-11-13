---
name: video-processor
description: Remove specified segments from a video and concatenate the remaining
  parts via ffmpeg trim/atrim+concat, producing `compressed_video.mp4` and a task-format
  `compression_report.json`.
---

## Steps
1. Treat the workflow as incomplete until **both** required artifacts exist in the current workspace and are validated: `compressed_video.mp4` and `compression_report.json`. Do not stop after an intermediate file.
2. Verify the input video exists and record its duration with ffprobe (also confirms the file is readable):
   ```bash
   ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 /path/to/input_video.mp4
   ```
3. Build a final removal list end-to-end (pipeline order):
   - `audio-extractor` → `energy-calculator` → `silence-detector` (opening) → `pause-detector` (start at opening end) → `segment-combiner` (then normalize/merge/clamp).
4. Process the video using the bundled processor script (workspace-relative path). Use the required output filename:
   ```bash
   python3 video-processor/scripts/process_video.py \
     --input /path/to/input_video.mp4 \
     --output compressed_video.mp4 \
     --remove-segments /path/to/all_segments.json
   ```
   (The script re-encodes with libx264 CRF 23 + AAC 128k.)
5. Generate the required report **separately** (the processor’s `<output>_report.json` has different keys than the task requires):
   ```bash
   python3 report-generator/scripts/generate_report.py \
     --original /path/to/input_video.mp4 \
     --compressed compressed_video.mp4 \
     --segments /path/to/all_segments.json \
     --output compression_report.json
   ```
6. If compression is off, retune and re-run from detection:
   - Opening too short/too long: adjust `silence-detector --threshold-multiplier` (higher ⇒ remove more opening; lower ⇒ remove less).
   - Pauses missed/too many: adjust `pause-detector --threshold-ratio` (higher ⇒ more pauses removed; lower ⇒ fewer) and/or `--min-duration`.

## Expected Result
`compressed_video.mp4` is playable with valid audio/video streams, and `compression_report.json` is parseable, schema-correct, and mathematically consistent (`original ≈ compressed + removed`) with sorted, non-overlapping, in-range removal segments.
