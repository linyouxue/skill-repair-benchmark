---
name: video-processor
description: Process videos by removing segments and concatenating remaining parts. Use when you need to remove detected pauses/openings from videos, create highlight reels, or batch process segment removals using ffmpeg filter_complex.
---

# Video Segment Processor

Processes videos by removing specified segments and concatenating the remaining parts. Handles multiple removal segments efficiently using ffmpeg's filter_complex.

## Use Cases

- Removing detected pauses and openings from videos
- Creating highlight reels by keeping only specific segments
- Batch processing multiple segment removals

## Usage

```bash
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input /path/to/input.mp4 \
    --output /path/to/output.mp4 \
    --remove-segments /path/to/segments.json
```

### Parameters

- `--input`: Path to input video file
- `--output`: Path to output video file
- `--remove-segments`: JSON file containing segments to remove

### Input Segment Format

```json
{
  "segments": [
    {"start": 0, "end": 600, "duration": 600},
    {"start": 610, "end": 613, "duration": 3}
  ]
}
```

Or multiple segment files:

```bash
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input video.mp4 \
    --output output.mp4 \
    --remove-segments opening.json pauses.json
```

## Output

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

1. **Load removal segments** from JSON file(s)
2. **Calculate keep segments** (inverse of removal segments)
3. **Build ffmpeg filter** to trim and concatenate
4. **Process video** using hardware-accelerated encoding
5. **Generate report** with statistics

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

## Performance Tips

- Use `-preset medium` for balanced speed/quality
- Use `-crf 23` for good quality at reasonable size
- Process on machines with 2+ CPU cores for faster encoding

## Notes

- Preserves video quality using CRF encoding
- Maintains audio sync throughout
- Handles edge cases (segments at start/end of the video)
- Generates detailed statistics for verification

### Critical correctness requirements (for evaluators that compare JSON ↔ video)

If you are producing a final deliverable (e.g., `compressed_video.mp4` plus a JSON report of removed segments), follow these rules so the report can be validated against the actual cut video:

1. **Segment time convention**: treat segments as **half-open intervals** `[start, end)` in seconds.
   - `start` is inclusive; `end` is exclusive.
   - `duration` **must** equal `end - start`.

2. **Preflight validation before running ffmpeg** (do this even if segments came from other detectors):
   - `0 <= start < end <= original_duration_seconds`
   - segments are sorted by `start`
   - segments **do not overlap** (ensure `prev.end <= next.start`)
   - merge/union segments that overlap or touch (otherwise you risk double-counting removed time and mismatched cuts)

3. **What you report must match what you cut**:
   - The segment list you pass to `--remove-segments` should be the **same list** (after sorting/merging) that you later place into `compression_report.json` as `segments_removed`.
   - Do not “recompute” or “approximate” segments for the report after cutting; use the exact normalized list used for processing.

4. **Rounding guidance**:
   - Detectors may output integer seconds; ffprobe durations are often fractional.
   - Prefer keeping `start/end` at integer seconds when derived from per-second energy, but always keep `duration=end-start` exact (as a number).

### End-to-end workflow reminder (common failure: missing outputs)

For a silence-removal task, the minimal reliable pipeline is:

1) extract audio → 2) compute energies → 3) detect opening + pauses → 4) combine/merge segments → 5) process video to `compressed_video.mp4` → 6) generate `compression_report.json` → 7) verify both files exist and are readable.
