---
name: silence-detector
description: Detect the initial “opening” low-energy section (pre-roll/title/setup)
  from energy data, with correct timestamp alignment when smoothing is enabled.
---

## Steps
1. Run the initial silence detector:
   ```bash
   python3 /root/.claude/skills/silence-detector/scripts/detect_silence.py \
     --energies /root/energies.json \
     --output /root/silence_raw.json \
     --threshold-multiplier 1.5 \
     --initial-window 60 \
     --smoothing-window 30
   ```
2. **Correct the timestamp alignment when `smoothing-window > 1`:**
   - The script smooths with `np.convolve(..., mode="valid")`, so `smoothed[i]` summarizes `energies[i : i + smoothing_window]`.
   - Therefore, the first index `i` where `smoothed[i] > threshold` is aligned to the **start** of that smoothing window, not its center.
   - Use an adjusted opening boundary for the original per-second timeline:
     - `opening_end = raw_end + (smoothing_window // 2)` (center-align; clamp to `[0, total_seconds]`).
   - Rewrite the output to `/root/silence.json` using this adjusted `opening_end` so downstream `--start-time` is consistent and you don’t accidentally detect leftover opening as many small pauses.
   Example adjustment:
   ```bash
   python3 - <<'PY'
   import json
   INP="/root/silence_raw.json"
   OUT="/root/silence.json"

   d=json.load(open(INP))
   segs=d.get("segments", [])
   if not segs:
       json.dump(d, open(OUT, "w"), indent=2)
       print("No opening detected; copied through.")
       raise SystemExit(0)

   raw_end=int(segs[0]["end"])
   w=int(d.get("parameters", {}).get("smoothing_window", 1))
   offset = (w // 2) if w > 1 else 0
   opening_end = raw_end + offset

   segs=[{"start": 0, "end": opening_end, "duration": opening_end}]
   d["segments"]=segs
   d["total_segments"]=1 if opening_end > 0 else 0
   d["total_duration_seconds"]=opening_end if opening_end > 0 else 0

   json.dump(d, open(OUT, "w"), indent=2)
   print(f"Adjusted opening end: {raw_end} -> {opening_end} (offset {offset}s)")
   PY
   ```
3. Parameter tuning (opening too long/short):
   - Lower `threshold_multiplier` ends the opening earlier (removes less).
   - Higher `threshold_multiplier` ends the opening later (removes more).
   - Larger `smoothing_window` is steadier but increases alignment sensitivity; if you change it, keep the alignment adjustment consistent.

## Expected Result
A `silence.json` with a single opening segment `[0, opening_end)` whose end is correctly aligned for use as the pause detector’s `--start-time` and for later segment merging.
