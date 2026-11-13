---
name: pause-detector
description: Detect low-energy pause segments using a local dynamic threshold (energy
  compared to surrounding context).
---

## Steps
1. Run pause detection on the energy JSON, starting *after the opening* (use the adjusted opening boundary described in `silence-detector`/`video-processor`):
   ```bash
   python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
     --energies /root/energies.json \
     --start-time <OPENING_END_SECONDS> \
     --min-duration 3 \
     --threshold-ratio 0.5 \
     --window-size 30 \
     --output /root/pauses.json
   ```
2. Tune for **precision** (reduce false positives / “over-removal”):
   - `threshold_ratio` is used as: `energy < local_avg * threshold_ratio`
     - **Lower `threshold_ratio` ⇒ more conservative** (harder to classify as low-energy; fewer segments).
     - **Higher `threshold_ratio` ⇒ more aggressive** (easier to classify as low-energy; more segments).
   - Because energies are in 1-second bins and the code uses `duration >= min_duration`, use:
     - `--min-duration 3` to target pauses “> 2s” and avoid many borderline 2s cuts.
     - Increase to `4` if you still see many short, natural pauses being removed.
3. Inspect the number of detected segments and whether many are exactly at the minimum duration; if so, tighten by lowering `threshold_ratio` and/or raising `min_duration`.

## Expected Result
A `pauses.json` with `segments` as `[start, end)` seconds (end-exclusive), each having `duration == end - start`, and fewer borderline 2-second false positives when tuned conservatively.
