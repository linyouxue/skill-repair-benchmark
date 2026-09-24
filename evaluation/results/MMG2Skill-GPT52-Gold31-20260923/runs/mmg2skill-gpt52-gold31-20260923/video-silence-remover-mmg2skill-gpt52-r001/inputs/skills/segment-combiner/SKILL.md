---
name: segment-combiner
description: Merge multiple removal-segment JSON files into one consolidated, sorted
  removal list for video processing.
---

## Steps
1. Combine opening + pauses into one removal file:
   ```bash
   python3 /root/.claude/skills/segment-combiner/scripts/combine_segments.py \
     --segments opening.json pauses.json \
     --output all_segments.json
   ```
2. Confirm output exists and is non-empty when removals are expected:
   - `ls -l all_segments.json`
   - `cat all_segments.json`
## Expected Result
`all_segments.json` exists with a single top-level `segments` array containing the unified removal segments.
