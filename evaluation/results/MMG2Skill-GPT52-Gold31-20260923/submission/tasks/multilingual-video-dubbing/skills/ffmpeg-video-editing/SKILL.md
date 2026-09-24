---
name: ffmpeg-video-editing
description: Perform basic video editing operations (cut/trim/split/concat) with FFmpeg.
---

## Steps
1. Cut/trim using timestamps:
   - `ffmpeg -ss 00:00:10 -to 00:00:30 -i input.mp4 -c copy output.mp4`
   - `ffmpeg -ss 00:00:10 -t 20 -i input.mp4 -c copy output.mp4`
2. Precise cutting (re-encode for accuracy):
   - `ffmpeg -ss 00:00:10 -i input.mp4 -t 20 -c:v libx264 -c:a aac output.mp4`
3. Concatenate (file-list method):
   - Create `list.txt` with `file 'video1.mp4'` lines, then:  
     `ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp4`
4. Split into time segments:
   - `ffmpeg -i input.mp4 -c copy -f segment -segment_time 60 -reset_timestamps 1 output_%03d.mp4`
## Expected Result
Video content is cut/trimmed/concatenated/split as needed, using stream copy when possible and re-encoding when precision is required.
