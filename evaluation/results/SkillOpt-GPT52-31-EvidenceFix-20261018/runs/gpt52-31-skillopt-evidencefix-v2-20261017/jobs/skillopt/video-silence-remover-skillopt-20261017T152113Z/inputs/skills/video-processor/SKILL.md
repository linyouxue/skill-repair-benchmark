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


Segment semantics are strict:

- `start`: inclusive timestamp in seconds where removal begins
- `end`: exclusive timestamp in seconds where removal stops
- `duration`: must equal `end - start`
- Use floating point seconds for sub-second cuts when needed
- Segments must be sorted by `start`
- Normalize overlapping or directly adjacent segments before processing to avoid duplicated removals or concat mismatches

Example normalization:

```json
[
  {"start": 10.0, "end": 12.0},
  {"start": 11.8, "end": 15.0},
  {"start": 15.0, "end": 16.0}
]
```

Should become:

```json
[
  {"start": 10.0, "end": 16.0, "duration": 6.0}
]
```
Or multiple segment files:

```bash
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input video.mp4 \
    --output output.mp4 \
    --remove-segments opening.json pauses.json
```

### Output

Creates the processed video and a report JSON:


For the `video-silence-remover` task, the final artifacts must be written exactly to the current workspace root as:

- `./compressed_video.mp4`
- `./compression_report.json`

The verifier checks these exact filenames and paths. Do not leave outputs in `/tmp`, nested directories, or use alternate names such as `compressed.mp4`.

The report schema must use:

```json
{
  "original_duration_seconds": 600.0,
  "compressed_duration_seconds": 480.0,
  "removed_duration_seconds": 120.0,
  "compression_percentage": 20.0,
  "segments_removed": [
    {
      "start": 0.0,
      "end": 12.5,
      "duration": 12.5
    }
  ]
}
```
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

## Example

```bash
# Process video with opening and pause removal
python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input /root/lecture.mp4 \
    --output /root/compressed.mp4 \
    --remove-segments /root/opening.json /root/pauses.json

# Result: 65 min → 51 min (21.2% compression)
```


Task-compliant example for the silence-removal benchmark:

```bash
# Combine detected opening + silence segments into one JSON
cat > /root/all_segments.json <<'JSON'
{
  "segments": [
    {"start": 0.0, "end": 8.2, "duration": 8.2},
    {"start": 120.4, "end": 123.1, "duration": 2.7}
  ]
}
JSON

python3 /root/.claude/skills/video-processor/scripts/process_video.py \
    --input /root/data/input_video.mp4 \
    --output ./compressed_video.mp4 \
    --remove-segments /root/all_segments.json
```

The `segments_removed` array written to `compression_report.json` must exactly match the actual removed regions used to generate `compressed_video.mp4`. Downstream verification reconstructs audio from the JSON and compares it against the produced video.
## Performance Tips

- Use `-preset medium` for balanced speed/quality
- Use `-crf 23` for good quality at reasonable size
- Process on machines with 2+ CPU cores for faster encoding

## Notes

- Preserves video quality using CRF encoding
- Maintains audio sync throughout
- Handles edge cases (segments at start/end of video)
- Generates detailed statistics for verification


## Validation Checklist

After processing, validate outputs before finishing:

```bash
test -f ./compressed_video.mp4
test -f ./compression_report.json

ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 ./compressed_video.mp4
```

Also verify:

- `original_duration_seconds ≈ compressed_duration_seconds + removed_duration_seconds`
- Every segment has `end > start`
- Every segment `duration` equals `end - start`
- Removed segments in JSON exactly correspond to the cuts applied by ffmpeg
- Sub-second trims are preserved consistently between JSON metadata and ffmpeg trim/atrim filters
