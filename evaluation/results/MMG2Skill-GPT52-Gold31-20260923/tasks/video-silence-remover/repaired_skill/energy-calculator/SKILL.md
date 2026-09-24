---
name: energy-calculator
description: Compute per-second RMS energy from a WAV file and save it as JSON for
  silence/pause detection.
---

## Steps
1. Run energy calculation:
   ```bash
   python3 /root/.claude/skills/energy-calculator/scripts/calc_energy.py \
     --audio audio.wav \
     --output energies.json
   ```
2. Sanity-check the output file exists and is readable:
   - `ls -l energies.json`
   - (Optional) `python3 -c "import json; d=json.load(open('energies.json')); print(d['total_seconds'], len(d['energies']))"`
## Expected Result
`energies.json` exists and contains `total_seconds` and an `energies` array aligned to 1-second windows.
