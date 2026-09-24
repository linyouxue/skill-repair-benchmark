---
name: video-processor
description: Remove specified time segments from a video and concatenate the remaining
  parts into a new video file.
---

## Steps
1. Process the input video using the unified removal segments and write the required deliverable name:
   ```bash
   python3 /root/.claude/skills/video-processor/scripts/process_video.py \
     --input data/input_video.mp4 \
     --output compressed_video.mp4 \
     --remove-segments all_segments.json
   ```
2. Confirm the output video exists:
   - `ls -l compressed_video.mp4`
3. (Optional) Quickly sanity-check duration is reduced:
   - `ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 data/input_video.mp4`
   - `ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 compressed_video.mp4`
## Expected Result
`compressed_video.mp4` exists in the current workspace with the opening and long pauses removed while retaining teaching content.
