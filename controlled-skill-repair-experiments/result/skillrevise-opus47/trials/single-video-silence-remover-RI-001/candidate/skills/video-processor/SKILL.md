---
name: video-processor
description: Process videos by removing segments and concatenating remaining parts. Use when you need to remove detected pauses/openings from videos, create highlight reels, or batch process segment removals using ffmpeg filter_complex.
---

# Video Segment Processor

Processes videos by removing specified segments and concatenating the remaining parts using ffmpeg filter_complex. For silence-removal tasks, this skill is the final stage of an audio-analysis -> segment-decision -> cut pipeline and owns the end-to-end completion gate.

## Blocking terminal-result gate

For silence-removal tasks, execution state is RED until terminal tool results confirm both required artifacts and every completion check below. While RED, every assistant response must include an actual terminal tool call for the next incomplete pipeline step; status prose may accompany the call but does not replace it. A command written only in prose, JSON, or a code block is still pending. State becomes GREEN only after tool results confirm the two required artifacts in the task-specified workspace path.

Discover the required output directory from the task instruction rather than assuming a fixed root. The two required artifacts are:

- compressed_video.mp4
- compression_report.json

## Mandatory end-to-end pipeline

Run as one ordered pipeline and do not stop at an intermediate checkpoint:

1. Probe the input video with ffprobe; record total_duration_seconds.
2. Extract audio to a working file.
3. Compute an audio energy sequence (both a raw per-window series and any smoothed series your detector uses). Keep the raw series available for cross-check.
4. Detect the non-teaching opening boundary B using the silence detector.
5. Validate B before using it (see "Opening-boundary validation" below). Use the validated boundary B* as the starting offset for long-pause detection.
6. Detect long pauses (default threshold > 2 s) in the region [B*, end].
7. Merge all removal segments: sort by start, clamp to [0, total_duration], drop zero/negative-length intervals, and merge only overlapping or touching intervals. Preserve every strictly positive gap.
8. Pre-encode plausibility check (see "Compression plausibility gate" below).
9. Cut and concatenate with ffmpeg filter_complex to produce the compressed video.
10. Measure the compressed video with ffprobe and generate the report from measured values (not planned values).
11. Run the completion checks and only then declare GREEN.

## Opening-boundary validation

The silence detector's smoothed boundary can be offset from the true crossing by roughly its smoothing-window length. Do not blindly trust the detector's default boundary.

Given detector output B, compute:

- R = first timestamp where the raw (unsmoothed) rolling energy sustains above the detector's threshold for at least one window.
- C = plausibility cap for the opening = max(60 s, 0.15 * total_duration_seconds).
- W = detector smoothing window in seconds.

Decision rule:

- If B <= C and |B - R| <= W: accept B* = B.
- Else if R <= C: use B* = R and log an override with reason "smoothing offset or plausibility cap".
- Else: use B* = min(R, C) and log "capped opening"; do not fabricate a boundary beyond signal evidence.

Record B, R, C, W, and B* in the agent log before proceeding. Never choose B* to hit a target total compression.

## Compression plausibility gate

Before encoding, compute predicted_removed = sum(duration of merged segments) and predicted_ratio = predicted_removed / total_duration_seconds.

- For a short (~10 min) teaching video with a brief opening and sparse pauses, expect predicted_ratio roughly in [0.02, 0.30].
- If predicted_ratio is outside that band, re-run Opening-boundary validation and re-check pause-detection thresholds against the signal (not against a target total). Proceed only after the re-check justifies the segments by evidence.

## Completion checks (must all pass before GREEN)

- Both required artifacts exist at the task-specified workspace path and are non-empty.
- ffprobe reads compressed_video.mp4 and reports valid video and audio streams.
- compression_report.json is parseable and contains: original_duration_seconds, compressed_duration_seconds, removed_duration_seconds, compression_percentage, segments_removed.
- Each item in segments_removed has numeric start < end and duration approximately equal to end - start (within 0.05 s).
- segments_removed is sorted by start and non-overlapping.
- Measured compressed duration (ffprobe) agrees with the report; original_duration_seconds approximately equals compressed_duration_seconds + removed_duration_seconds (within ~0.5 s).
- Agent log contains B, R, C, W, B*, and predicted_ratio values from the validation and plausibility gates.

If any check fails, repair the specific failing stage and re-run subsequent stages; do not switch output paths silently.

## Usage

```bash
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input <input_video> \
    --output <output_video> \
    --remove-segments <segments.json> [<more_segments.json> ...]
```

### Parameters

- `--input`: Path to input video file (discover from task instruction).
- `--output`: Path to output video file (use task-specified workspace path).
- `--remove-segments`: One or more JSON files listing segments to remove.

### Input Segment Format

```json
{
  "segments": [
    {"start": 0, "end": 75, "duration": 75},
    {"start": 180, "end": 183, "duration": 3}
  ]
}
```

(Values above are illustrative only; derive real values from signal evidence for the current input.)

### Script output

The helper script produces the compressed video plus an internal statistics JSON. The task-format compression_report.json must be generated separately from measured ffprobe durations and the final merged segment list, matching the task's required key names exactly.

## How It Works

1. Load removal segments from JSON file(s).
2. Compute keep segments as the complement of removal segments over [0, total_duration].
3. Build an ffmpeg filter_complex that trims and concatenates keep segments for both video and audio.
4. Encode with libx264 + aac (CRF-based) and remux.
5. Measure the result and emit statistics.

### FFmpeg filter pattern

```
[0:v]trim=start=S0:end=E0,setpts=PTS-STARTPTS[v0];
[0:a]atrim=start=S0:end=E0,asetpts=PTS-STARTPTS[a0];
...
[v0][v1]...concat=n=N:v=1:a=0[outv];
[a0][a1]...concat=n=N:v=0:a=1[outa]
```

## Dependencies

- ffmpeg with libx264 and aac support.
- ffprobe for duration and stream validation.
- Python 3.11+.

## Constraints

- Do not hard-code input or output paths; read them from the task instruction.
- Do not pick thresholds, smoothing windows, or opening boundaries to achieve a target compression percentage.
- Do not drop positive gaps between detected segments.
- Do not accept an opening boundary that violates the plausibility cap without a logged, evidence-based override.
- Do not silently relocate outputs if a write fails; inspect permissions and the task-specified workspace path first.

## Limitations

- Processing time scales roughly with video duration; keep encoder preset reasonable to stay under the task time budget.
- Cuts are frame-accurate, not sample-accurate; expect small (sub-second) drift between planned and measured durations, which the report must reflect from measured values.