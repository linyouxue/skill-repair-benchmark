---
name: video-processor
description: Remove specified segments from a video and concatenate the remainder
  into `compressed_video.mp4`, then generate the task-format `compression_report.json`
  from the final merged segment list.
---

## Steps
1. **Blocking terminal-result gate (must-follow in execution runs):**
   - Execution state is **RED** until terminal tool results confirm both required artifacts and every completion check below.
   - While state is RED, every assistant response must include an actual `terminal` tool call for the next incomplete pipeline action.
   - A command written in prose, JSON, or a code block is still pending because it has no terminal result.
   - Advance a step only after its real tool result returns.
   - State becomes **GREEN** only after tool results confirm:
     - `/root/compressed_video.mp4`
     - `/root/compression_report.json`
2. **Mandatory end-to-end pipeline (use these skills in order):**
   1. Extract audio (`audio-extractor`) to `/root/audio.wav`.
   2. Calculate energy (`energy-calculator`) to `/root/energies.json` (keep 1s windows unless you also change time mapping everywhere).
   3. Detect opening (`silence-detector`) and **apply the smoothing-window timestamp alignment** to produce `/root/silence.json`.
      - Use the adjusted `opening_end` as the boundary for pause detection.
   4. Detect pauses (`pause-detector`) starting at `opening_end` with **precision-oriented settings**:
      - Prefer `--min-duration 3` (or `4`) to avoid removing borderline natural 2s pauses.
      - Remember: lower `threshold_ratio` is more conservative; higher is more aggressive.
   5. Combine + merge removal segments:
      - Use `segment-combiner` to create `/root/all_segments.json`.
      - Ensure segments follow `[start, end)` convention, are merged (union), sorted, non-overlapping, and have `duration == end - start`.
   6. Process the video using the final merged segments list:
      ```bash
      python3 /root/.claude/skills/video-processor/scripts/process_video.py \
        --input data/input_video.mp4 \
        --output /root/compressed_video.mp4 \
        --remove-segments /root/all_segments.json
      ```
   7. Generate the required task report from the *actual* outputs (do not rely on `process_video.py`’s internal `_report.json` for the task schema):
      ```bash
      python3 /root/.claude/skills/report-generator/scripts/generate_report.py \
        --original data/input_video.mp4 \
        --compressed /root/compressed_video.mp4 \
        --segments /root/all_segments.json \
        --output /root/compression_report.json
      ```
   8. Verify outputs and iterate if needed (tighten detection to improve precision before re-rendering):
      - both files exist and are non-empty
      - `ffprobe` reads `/root/compressed_video.mp4` and shows valid video+audio streams
      - JSON parseable and contains:
        `original_duration_seconds`, `compressed_duration_seconds`,
        `removed_duration_seconds`, `compression_percentage`, `segments_removed`
      - `segments_removed` sorted & non-overlapping; each has numeric `start < end` and `duration == end - start`
      - math consistency: `original ≈ compressed + removed` (using measured durations)
3. **Segment hygiene expectations for this processor (to avoid invalid edits):**
   - Provide removal segments that are already merged (no nesting/overlap) and in `[start, end)` seconds.
   - If you change pause detection parameters, re-run segment merge before processing so the report matches what was actually removed.

## Expected Result
A processed `/root/compressed_video.mp4` with the opening and long non-teaching pauses removed (without excessive false-positive cuts), plus `/root/compression_report.json` matching the required schema and consistent with the actual video durations and the final merged segments list.
