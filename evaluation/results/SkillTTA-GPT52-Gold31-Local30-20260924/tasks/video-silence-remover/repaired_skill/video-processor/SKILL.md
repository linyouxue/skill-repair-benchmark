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
# Recommended (robust): run ffmpeg directly with a generated filter_complex.
# This avoids common failure modes like incorrect ffmpeg flag ordering,
# unmerged/overlapping segments, and empty keep-timelines.
python3 - <<'PY'
import json, subprocess

input_path = "/path/to/input.mp4"
segments_path = "/path/to/segments.json"  # expects {"segments": [{"start":..,"end":..}, ...]}
output_path = "/path/to/output.mp4"

# Probe duration
cmd_dur = ["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1", input_path]
dur = float(subprocess.check_output(cmd_dur).decode().strip())

# Load + normalize segments
data = json.load(open(segments_path))
raw = data.get("segments", [])
segs = []
for s in raw:
    st = float(s["start"]); en = float(s["end"])
    st = max(0.0, min(st, dur)); en = max(0.0, min(en, dur))
    if en > st:
        segs.append([st, en])
segs.sort()

# Merge overlaps/adjacent
merged = []
EPS = 0.05
for st, en in segs:
    if not merged or st > merged[-1][1] + EPS:
        merged.append([st, en])
    else:
        merged[-1][1] = max(merged[-1][1], en)

# Compute keep segments (complement)
keep = []
t = 0.0
for st, en in merged:
    if st > t:
        keep.append((t, st))
    t = max(t, en)
if t < dur:
    keep.append((t, dur))

# If nothing to keep, fall back to a no-op (copy) rather than crashing
if not keep:
    subprocess.run(["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path], check=True)
    raise SystemExit(0)

# Build filter_complex
parts = []
for i, (st, en) in enumerate(keep):
    parts.append(f"[0:v]trim=start={st}:end={en},setpts=PTS-STARTPTS[v{i}]")
    parts.append(f"[0:a]atrim=start={st}:end={en},asetpts=PTS-STARTPTS[a{i}]")
vin = "".join([f"[v{i}]" for i in range(len(keep))])
ain = "".join([f"[a{i}]" for i in range(len(keep))])
parts.append(f"{vin}concat=n={len(keep)}:v=1:a=0[outv]")
parts.append(f"{ain}concat=n={len(keep)}:v=0:a=1[outa]")
fc = ";".join(parts)

subprocess.run([
    "ffmpeg", "-y", "-i", input_path,
    "-filter_complex", fc,
    "-map", "[outv]", "-map", "[outa]",
    "-c:v", "libx264", "-preset", "medium", "-crf", "23",
    "-c:a", "aac", "-b:a", "128k",
    output_path,
], check=True)
PY
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

## Performance Tips

- Use `-preset medium` for balanced speed/quality
- Use `-crf 23` for good quality at reasonable size
- Process on machines with 2+ CPU cores for faster encoding

## Notes

- Preserves video quality using CRF encoding
- Maintains audio sync throughout
- Handles edge cases (segments at start/end of video)
- Generates detailed statistics for verification
