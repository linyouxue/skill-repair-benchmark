---
name: video-processor
description: Process videos by removing segments and concatenating remaining parts. Use when you need to remove detected pauses/openings from videos, create highlight reels, or batch process segment removals using ffmpeg filter_complex.
---

# Video Segment Processor

## Blocking terminal-result gate

For `video-silence-remover`, execution state is **RED** until terminal tool results confirm both required artifacts and every completion check below. While state is RED, every assistant response must include an actual `terminal` function call for the next incomplete pipeline action; status text may accompany that call.

A command written in prose, JSON, or a code block is still pending because it has no terminal result. Advance a step only after its real tool result returns. State becomes **GREEN** only after tool results confirm `/root/compressed_video.mp4` and `/root/compression_report.json`; an ordinary final response is valid only in GREEN state.

Processes videos by removing specified segments and concatenating the remaining parts. Handles multiple removal segments efficiently using ffmpeg's filter_complex.

## Mandatory end-to-end completion gate

For a silence-removal task, treat the available audio and video skills as one ordered pipeline. Continue issuing tool calls until both final artifacts pass the completion checks:

1. Extract the input video's audio.
2. Calculate the audio-energy sequence.
3. Detect the non-teaching opening with the silence detector's result (center-aligned seconds, see `silence-detector/SKILL.md`), then start long-pause detection at that returned boundary.
4. **Always run `segment-combiner`** on all detector outputs with
   `--gap-tolerance 0.3` and `--duration <probed_duration>` so the
   removal list is sorted, merged, de-overlapped, and clamped to the
   actual video length. Do **not** pass raw detector outputs directly to
   `process_video.py`.
5. Process the original video with the combined segments to create the compressed video. `process_video.py` additionally applies a defensive merge+clamp pass and asserts that `|original - (compressed + removed)| < 0.5s`.
6. Generate the task-format compression report from the actual original video, compressed video, and final (merged+clamped) segment list.
7. Verify both outputs with tools and repair any failed check.

For `video-silence-remover`, completion requires both `/root/compressed_video.mp4` and `/root/compression_report.json`. Before finishing, confirm that:

- both files exist and are non-empty;
- `ffprobe` can read the compressed video and reports valid video and audio streams;
- the JSON is parseable and contains `original_duration_seconds`, `compressed_duration_seconds`, `removed_duration_seconds`, `compression_percentage`, and `segments_removed`;
- every removed segment has numeric `start < end` and `duration ≈ end - start`, and the segments are sorted and non-overlapping;
- the measured compressed duration agrees with the report and `original ≈ compressed + removed` (within 0.5s).

Each intermediate audio, energy, or segment file is a checkpoint, not the completion criterion. After deciding or describing the next action, perform it with a tool call. Finish only after the two final artifacts pass these checks.

## Shared threshold flag

There is no single `--threshold-ratio` on `process_video.py` itself; the
knob lives on the two detectors:

- `silence-detector --threshold-multiplier` multiplies a **global**
  baseline (mean of the initial window). Default `1.5`.
- `pause-detector --threshold-ratio` is a fraction of a **local median**
  reference. Default `0.3`.

These are *not* numerically interchangeable; configure each independently
but keep both consistent with the task's noise characteristics.

## Use Cases

- Removing detected pauses and openings from videos
- Creating highlight reels by keeping only specific segments
- Batch processing multiple segment removals

## Usage

```bash
# Preferred: feed the merged+clamped output of segment-combiner
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input /path/to/input.mp4 \
    --output /path/to/output.mp4 \
    --remove-segments /path/to/all_segments.json
```

### Parameters

- `--input`: Path to input video file
- `--output`: Path to output video file
- `--remove-segments`: JSON file(s) containing segments to remove.
  Should already be the output of `segment-combiner` (sorted,
  non-overlapping, clamped). A defensive merge+clamp pass is applied
  regardless.

### Input Segment Format

```json
{
  "segments": [
    {"start": 0, "end": 600, "duration": 600},
    {"start": 610, "end": 613, "duration": 3}
  ]
}
```

### Output

Creates the processed video and a report JSON:

```json
{
  "original_duration": 3908.61,
  "output_duration": 3078.61,
  "removed_duration": 830.0,
  "compression_percentage": 21.24,
  "segments_removed": 91,
  "segments_kept": 91
}
```

## How It Works

1. **Load removal segments** from JSON file(s).
2. **Defensively merge + clamp** segments (sort, merge overlaps with a
   0.3s gap tolerance, clamp to `[0, total_duration]`). This protects
   against callers who skipped `segment-combiner`.
3. **Calculate keep segments** (inverse of removal segments).
4. **Build ffmpeg filter** to trim and concatenate.
5. **Process video** using libx264/aac.
6. **Assert** `|original - (output + removed)| < 0.5s` and generate a
   stats JSON next to the output file.

### FFmpeg Filter Example

For 3 segments to keep:
```
[0:v]trim=start=600:end=610,setpts=PTS-STARTPTS[v0];
[0:a]atrim=start=600:end=610,asetpts=PTS-STARTPTS[a0];
[0:v]trim=start=613:end=1000,setpts=PTS-STARTPTS[v1];
[0:a]atrim=start=613:end=1000,asetpts=PTS-STARTPTS[a1];
[v0][v1]concat=n=2:v=1:a=0[outv];
[a0][a1]concat=n=2:v=0:a=1[outa]
```

## Dependencies

- ffmpeg with libx264 and aac support
- Python 3.11+

## Limitations

- Processing time: ~0.3× video duration (e.g., 20 min for 65 min video)
- Requires sufficient disk space (output ≈ 70-80% of input size)
- May have frame-accurate cuts (not sample-accurate)

## Example

```bash
# 1. Combine detector outputs with merge + clamp
python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
    --segments /root/opening.json /root/pauses.json \
    --duration "$(ffprobe -v error -show_entries format=duration -of csv=p=0 /root/lecture.mp4)" \
    --output /root/all_segments.json

# 2. Process video with the combined list
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input /root/lecture.mp4 \
    --output /root/compressed.mp4 \
    --remove-segments /root/all_segments.json
```

## Performance Tips

- Use `-preset medium` for balanced speed/quality
- Use `-crf 23` for good quality at reasonable size
- Process on machines with 2+ CPU cores for faster encoding

## Notes

- Preserves video quality using CRF encoding
- Maintains audio sync throughout
- Handles edge cases (segments at start/end of video)
- Generates detailed statistics for verification
