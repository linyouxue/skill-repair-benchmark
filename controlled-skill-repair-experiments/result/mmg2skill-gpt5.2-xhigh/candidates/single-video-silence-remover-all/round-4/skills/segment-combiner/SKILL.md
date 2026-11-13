---
name: segment-combiner
description: Combine multiple detector outputs into a single removal list, then merge
  intervals to reduce fragmentation and avoid precision loss from over-segmentation.
---

## Steps
1. Combine detector outputs (this script **concatenates + sorts**; it does not “union-merge” by itself):
   ```bash
   python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
     --segments /root/silence.json /root/pauses.json \
     --output /root/all_segments_raw.json
   ```
2. Merge intervals using the project convention:
   - Treat segments as **half-open** intervals: `[start, end)` in seconds.
   - Merge when `next.start <= current.end` (overlap/touch).
   - To reduce fragmentation from 1-second energy quantization (improves benchmark **precision**), optionally also merge across tiny gaps by using a `gap_tolerance` (commonly `1` second): merge when `next.start <= current.end + gap_tolerance`.
   - After merging, always recompute `duration = end - start`.
   Example merge post-process (edit `GAP` as needed):
   ```bash
   python3 - <<'PY'
   import json
   INP="/root/all_segments_raw.json"
   OUT="/root/all_segments.json"
   GAP=1  # 0 = only overlap/touch; 1 = also merge 1s gaps to reduce fragmentation

   data=json.load(open(INP))
   segs=sorted(data.get("segments", []), key=lambda s: s["start"])

   merged=[]
   for s in segs:
       a=float(s["start"]); b=float(s["end"])
       if b <= a:
           continue
       if (not merged) or (a > merged[-1]["end"] + GAP):
           merged.append({"start": a, "end": b})
       else:
           merged[-1]["end"] = max(merged[-1]["end"], b)

   def norm(x):
       r=round(x)
       return int(r) if abs(x-r) < 1e-6 else float(x)

   for m in merged:
       m["start"]=norm(m["start"])
       m["end"]=norm(m["end"])
       m["duration"]=m["end"]-m["start"]

   out={
       "segments": merged,
       "total_segments": len(merged),
       "total_duration_seconds": sum(m["duration"] for m in merged),
   }
   json.dump(out, open(OUT, "w"), indent=2)
   print(f"Wrote {OUT}: {len(merged)} merged segments")
   PY
   ```
3. Quick validity check before video processing:
   - sorted by `start`
   - non-overlapping after merge
   - each has numeric `start < end` and `duration == end - start`

## Expected Result
A single `all_segments.json` containing a de-fragmented, merged removal list that is more likely to match ground truth segment granularity (higher precision).
