---
name: silence-detector
description: Detect the initial low-energy opening segment (pre-roll silence/title)
  from precomputed energy data.
---

## Steps
1. Run initial silence/opening detection (execute as a normal shell command, not embedded inside JSON text):
   ```bash
   python3 /root/.claude/skills/silence-detector/scripts/detect_silence.py \
     --energies energies.json \
     --output opening.json
   ```
2. Verify the detector actually produced output and inspect it:
   - `ls -l opening.json`
   - `cat opening.json`
## Expected Result
`opening.json` exists and contains a `segments` list (often a single segment starting at `0`) representing the opening to remove.
