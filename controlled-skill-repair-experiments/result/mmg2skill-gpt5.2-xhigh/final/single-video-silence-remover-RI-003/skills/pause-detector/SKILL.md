---
name: pause-detector
description: Detect long low-energy pauses using a local dynamic threshold on precomputed
  energy data (robust to volume changes across a lecture).
---

## Steps
1. Decide where to begin pause detection:
   - Use `--start-time <opening_end>` to skip the non-teaching opening (where `<opening_end>` comes from `silence-detector`), otherwise use `0`.
2. Run the bundled pause detector from the workspace:
   ```bash
   python3 pause-detector/scripts/detect_pauses.py \
     --energies /path/to/energies.json \
     --output /path/to/pauses.json \
     --start-time <seconds> \
     --threshold-ratio 0.5 \
     --min-duration 2 \
     --window-size 30
   ```
3. Tune parameters (match the script’s condition `energy < local_avg * threshold_ratio`):
   - `threshold_ratio`: a second is a “pause” when its energy is below a **fraction of the local average**.  
     Increase the ratio (e.g., `0.5 → 0.7`) ⇒ threshold rises ⇒ **more** seconds/segments detected as pauses (more aggressive removal).  
     Decrease the ratio (e.g., `0.5 → 0.3`) ⇒ threshold drops ⇒ **fewer** pauses detected (more conservative, fewer false positives).
   - `min_duration`: increase ⇒ only longer pauses are removed; decrease ⇒ more (shorter) pauses are removed.
4. Confirm segments look valid: numeric `start < end`, `duration == end - start`, and times are within the video duration.

## Expected Result
A `pauses.json` containing a `segments` list of disjoint low-energy intervals (seconds) meeting the minimum duration.
