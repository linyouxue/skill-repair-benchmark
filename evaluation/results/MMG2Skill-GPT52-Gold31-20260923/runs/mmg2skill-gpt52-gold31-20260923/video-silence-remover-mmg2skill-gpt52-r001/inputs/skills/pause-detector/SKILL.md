---
name: pause-detector
description: Detect >2s low-energy pauses (silences) throughout the teaching content
  using local dynamic thresholds.
---

## Steps
1. Run pause detection using the default minimum duration (2 seconds) unless tuning is needed:
   ```bash
   python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
     --energies energies.json \
     --output pauses.json
   ```
2. Verify the pauses file was created and inspect segments:
   - `ls -l pauses.json`
   - `cat pauses.json`
3. If an opening segment was found, re-run pause detection skipping the opening (so you don’t double-remove it):
   ```bash
   python3 /root/.claude/skills/pause-detector/scripts/detect_pauses.py \
     --energies energies.json \
     --start-time <opening_end_second> \
     --output pauses.json
   ```
## Expected Result
`pauses.json` exists and lists pause segments (each with `start`, `end`, `duration`) primarily capturing long pauses while preserving teaching content.
