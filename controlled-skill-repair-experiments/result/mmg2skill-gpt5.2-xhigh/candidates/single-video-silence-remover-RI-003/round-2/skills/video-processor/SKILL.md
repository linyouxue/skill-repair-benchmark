---
name: video-processor
description: Remove specified segments from a video and concatenate the remaining
  parts via ffmpeg trim/atrim+concat, producing `compressed_video.mp4` and a task-format
  `compression_report.json`.
---

## Steps
1. Treat the workflow as incomplete until **both** required artifacts exist in the current workspace and are validated: `compressed_video.mp4` and `compression_report.json`. Do not stop after an intermediate file.
2. Verify the input video exists and record its duration with ffprobe (also confirms the file is readable). For this task, the input is `data/input_video.mp4`:
   ```bash
   ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 data/input_video.mp4
   ```
3. Build a final removal list end-to-end by **running** the provided scripts directly from the workspace (no need to search hidden folders; tools are in `*/scripts/*.py`). Use workspace-local filenames so the later steps are copy/pasteable:
   ```bash
   python3 audio-extractor/scripts/extract_audio.py --video data/input_video.mp4 --output audio.wav
   python3 energy-calculator/scripts/calc_energy.py --audio audio.wav --output energies.json --window-seconds 1
   python3 silence-detector/scripts/detect_silence.py --energies energies.json --output initial_silence.json --threshold-multiplier 1.5 --initial-window 60 --smoothing-window 30
   # set <opening_end> to initial_silence.json: segments[0].end (or 0 if segments is empty)
   python3 pause-detector/scripts/detect_pauses.py --energies energies.json --output pauses.json --start-time <opening_end> --threshold-ratio 0.5 --min-duration 2 --window-size 30
   python3 segment-combiner/scripts/combine_segments.py --segments initial_silence.json pauses.json --output all_segments.json
   ```
   Then run the `segment-combiner` normalization/merge/clamp step so `all_segments.json` is sorted, in-range, and non-overlapping.
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
   - Opening too short: increase `silence-detector --threshold-multiplier`. Opening too long: decrease it.
   - Too few pauses detected: increase `pause-detector --threshold-ratio` and/or decrease `--min-duration`.  
     Too many/false pauses (cutting real speech): decrease `--threshold-ratio` and/or increase `--min-duration`.

## Expected Result
`compressed_video.mp4` is playable with valid audio/video streams, and `compression_report.json` is parseable, schema-correct, and mathematically consistent (`original ≈ compressed + removed`) with sorted, non-overlapping, in-range removal segments.
