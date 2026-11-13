---
name: silence-detector
description: Detect the initial non-teaching opening (low-energy lead-in) using energy
  thresholding with smoothing, and output it as a removable segment list.
---

## Steps
1. Run initial silence detection (workspace-relative script path):
   ```bash
   python3 silence-detector/scripts/detect_silence.py \
     --energies /path/to/energies.json \
     --output /path/to/initial_silence.json \
     --threshold-multiplier 1.5 \
     --initial-window 60 \
     --smoothing-window 30
   ```
2. Tune parameters (in terms of opening removal length, using `threshold = initial_avg * threshold_multiplier` and “opening ends” at the first `smoothed_energy > threshold`):
   - `threshold_multiplier`: increase ⇒ threshold higher ⇒ opening ends later ⇒ removes **more** opening; decrease ⇒ removes **less** opening (and can help if the threshold is so high that no transition is found).
   - `initial_window`: should mostly cover the true opening; if it includes speech, the baseline rises and opening detection can fail.
   - `smoothing_window`: higher smooths more but can shift/blur the transition.
3. Use the detected opening end directly as `pause-detector --start-time`. The script already aligns a `valid` moving-average crossing to the center of its source window; use the returned segment end as-is.

## Expected Result
An `initial_silence.json` with either an empty `segments` list (no clear opening) or a single segment `{start:0, end:<opening_end>, duration:<opening_end>}`.
