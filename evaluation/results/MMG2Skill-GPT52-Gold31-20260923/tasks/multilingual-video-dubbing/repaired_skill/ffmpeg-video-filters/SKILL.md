---
name: ffmpeg-video-filters
description: Apply common video filters (scale/crop/overlay/speed/blur/eq/fade) using
  FFmpeg.
---

## Steps
1. Scale:
   - `ffmpeg -i input.mp4 -vf scale=-2:720 output.mp4`
2. Crop:
   - `ffmpeg -i input.mp4 -vf "crop=800:600:100:50" output.mp4`
3. Overlay watermark/logo:
   - `ffmpeg -i input.mp4 -i logo.png -filter_complex "overlay=W-w-10:H-h-10" output.mp4`
4. Speed change (video + audio):
   - `ffmpeg -i input.mp4 -vf "setpts=0.5*PTS" -af "atempo=2.0" output.mp4`
5. Blur / EQ / fades as needed:
   - Blur: `-vf "boxblur=10:5"`
   - Fade: `-vf "fade=t=in:st=0:d=2"`
## Expected Result
Video is transformed visually as required while maintaining compatibility with downstream muxing/delivery.
