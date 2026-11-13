---
name: energy-calculator
description: 'Compute per-window (default: 1s) RMS energy from a WAV file and save
  an energy timeline JSON for pause/opening detection.'
---

## Steps
1. Ensure the input is a WAV (ideally from `audio-extractor`, mono 16kHz PCM).
2. Run the bundled script from the workspace:
   ```bash
   python3 energy-calculator/scripts/calc_energy.py \
     --audio /path/to/audio.wav \
     --output /path/to/energies.json \
     --window-seconds 1
   ```
3. Sanity-check `energies.json`: `energies` should be an array of numbers; `total_seconds` should be close to the audio duration (may be slightly larger due to the final partial window).

## Expected Result
An `energies.json` containing `energies` plus basic stats, suitable input for `silence-detector` and `pause-detector`.
