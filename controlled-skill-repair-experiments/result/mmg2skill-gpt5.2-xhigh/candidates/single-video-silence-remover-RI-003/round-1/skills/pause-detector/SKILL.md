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
3. Tune parameters (correct semantics):
   - `threshold_ratio`: a second is “pause” when `energy < local_avg * threshold_ratio`.  
     **Higher** ratio ⇒ higher cutoff ⇒ **more** seconds counted as pause (more aggressive removal).  
     **Lower** ratio ⇒ fewer pauses detected (more conservative).
   - `min_duration`: higher ⇒ fewer segments (only longer pauses); lower ⇒ more segments (includes shorter pauses).
4. Confirm segments look valid: numeric `start < end`, `duration == end - start`, and times are within the video duration.

## Expected Result
A `pauses.json` containing a `segments` list of disjoint low-energy intervals (seconds) meeting the minimum duration.
