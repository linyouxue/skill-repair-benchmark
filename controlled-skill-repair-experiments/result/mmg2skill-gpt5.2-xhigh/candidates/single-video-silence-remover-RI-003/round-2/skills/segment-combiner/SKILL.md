---
name: segment-combiner
description: Combine multiple segment JSON outputs into one normalized, sorted, non-overlapping
  removal list for video processing and reporting.
---

## Steps
1. Combine detector outputs (workspace-relative script path):
   ```bash
   python3 segment-combiner/scripts/combine_segments.py \
     --segments /path/to/initial_silence.json /path/to/pauses.json \
     --output /path/to/all_segments.json
   ```
2. Normalize the combined segments into a clean removal list (sorted; clamped to video duration; merge only overlapping/touching intervals; recompute `duration=end-start`). Example in-place normalizer:
   ```bash
   python3 - <<'PY'
   import json, subprocess

   video = "/path/to/original.mp4"
   seg_path = "/path/to/all_segments.json"

   dur = float(subprocess.check_output([
       "ffprobe","-v","error","-show_entries","format=duration",
       "-of","default=nw=1:nk=1", video
   ]).decode().strip())

   data = json.load(open(seg_path))
   segs = data.get("segments", [])

   # clamp + filter
   norm = []
   for s in segs:
       a = max(0.0, float(s["start"]))
       b = min(dur, float(s["end"]))
       if b > a:
           norm.append({"start": a, "end": b})
   norm.sort(key=lambda x: x["start"])

   # merge overlaps/touching only (preserve every positive gap)
   merged = []
   for s in norm:
       if not merged or s["start"] > merged[-1]["end"]:
           merged.append(s)
       else:
           merged[-1]["end"] = max(merged[-1]["end"], s["end"])

   for s in merged:
       s["duration"] = round(s["end"] - s["start"], 3)

   out = {
       "segments": merged,
       "total_segments": len(merged),
       "total_duration_seconds": round(sum(s["duration"] for s in merged), 3),
   }
   json.dump(out, open(seg_path, "w"), indent=2)
   PY
   ```
   (This preserves every positive gap; it merges only when `next.start <= current.end`.)
3. Re-check: segments are sorted, non-overlapping, within `[0, video_duration]`, and each has `duration == end - start`.

## Expected Result
A single `all_segments.json` ready for `video-processor` and `report-generator`, with valid non-overlapping removal segments.
