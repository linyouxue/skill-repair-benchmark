---
name: energy-calculator
description: Compute RMS energy in fixed time windows (typically 1s) from a WAV file
  and save it as JSON for silence/pause detectors.
---

## Steps
1. Run the energy calculator (keep `--window-seconds 1` unless you also update downstream time interpretation):
   ```bash
   python3 /root/.claude/skills/energy-calculator/scripts/calc_energy.py \
     --audio /root/audio.wav \
     --output /root/energies.json \
     --window-seconds 1
   ```
2. Use the printed stats (`min/max/mean/std`) to sanity-check that energies are non-zero and have dynamic range (helps later threshold tuning).

## Expected Result
An `energies.json` containing `window_seconds`, `total_seconds`, and an `energies` array whose indices correspond to (approximately) seconds on the video timeline.
