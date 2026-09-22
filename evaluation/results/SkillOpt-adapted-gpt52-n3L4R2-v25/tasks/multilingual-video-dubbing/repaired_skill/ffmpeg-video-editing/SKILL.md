---
name: ffmpeg-video-editing
description: Cut, trim, concatenate, and split video files - basic video editing operations
---

# FFmpeg Video Editing Skill

Basic video editing operations: cutting, trimming, concatenating, and splitting videos.

## When to Use

- Cut segments from video
- Trim video length
- Concatenate multiple videos
- Split video into parts
- Extract specific time ranges

## Cutting and Trimming

```bash
# Cut from 10s to 30s (using -ss and -to)
ffmpeg -ss 00:00:10 -to 00:00:30 -i input.mp4 -c copy output.mp4

# Cut from 10s for 20 seconds duration
ffmpeg -ss 00:00:10 -t 20 -i input.mp4 -c copy output.mp4

# First 60 seconds
ffmpeg -t 60 -i input.mp4 -c copy output.mp4

# Last 30 seconds (need duration first)
ffmpeg -sseof -30 -i input.mp4 -c copy output.mp4
```

## Precise Cutting

```bash
# With re-encoding (more precise)
ffmpeg -ss 00:00:10 -i input.mp4 -t 20 -c:v libx264 -c:a aac output.mp4

# Keyframe-accurate (faster, may be less precise)
ffmpeg -ss 00:00:10 -i input.mp4 -t 20 -c copy output.mp4
```

## Concatenation

### Method 1: File List (Recommended)

```bash
# Create list.txt file:
# file 'video1.mp4'
# file 'video2.mp4'
# file 'video3.mp4'

ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp4
```

### Method 2: Same Codec Files

```bash
# If all videos have same codec/format
ffmpeg -i "concat:video1.mp4|video2.mp4|video3.mp4" -c copy output.mp4
```

### Method 3: Re-encode (Different Codecs)

```bash
# Re-encode for compatibility
ffmpeg -f concat -safe 0 -i list.txt -c:v libx264 -c:a aac output.mp4
```

## Splitting Video

```bash
# Split into 60-second segments
ffmpeg -i input.mp4 -c copy -f segment -segment_time 60 \
  -reset_timestamps 1 output_%03d.mp4

# Split at specific timestamps
ffmpeg -i input.mp4 -ss 00:00:00 -t 00:01:00 -c copy part1.mp4
ffmpeg -i input.mp4 -ss 00:01:00 -t 00:01:00 -c copy part2.mp4
```

## Extract Segment with Re-encoding

```bash
# When you need to change quality/codec
ffmpeg -ss 00:00:10 -i input.mp4 -t 20 \
  -c:v libx264 -crf 23 -c:a aac -b:a 192k output.mp4
```

## Multiple Segments

```bash
# Extract multiple segments
ffmpeg -i input.mp4 \
  -ss 00:00:10 -t 00:00:05 -c copy segment1.mp4 \
  -ss 00:01:00 -t 00:00:10 -c copy segment2.mp4
```

## Notes

- Use `-c copy` for speed (no re-encoding)
- `-ss` before `-i` is faster but less precise
- `-ss` after `-i` is more precise but slower
- Concatenation requires same codec/format for `-c copy`
- Use file list method for best concatenation results


## Multilingual Dubbing Mux and Delivery

When replacing the audio of a video with a prepared dubbed track, use explicit stream maps so the source audio cannot be included accidentally:

1. Obtain the source container duration and the first video stream properties before muxing:

```bash
SOURCE_DURATION_SEC=$(ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 /root/input.mp4)
ffprobe -v error -show_entries format=duration:stream=index,codec_type,codec_name,width,height,pix_fmt,r_frame_rate,start_time,duration \
  -of json /root/input.mp4 > /outputs/source_mux_probe.json
```

The prepared dubbed WAV must represent the complete source timeline, start at timeline zero, and already be 48000 Hz mono. If its timestamps are not zero-based, normalize them before muxing with `asetpts=PTS-STARTPTS`; do not apply an input offset unless the offset is explicitly part of the verified timeline. The source audio is not an input to the mux operation.

2. Mux the original visual stream with only the prepared dubbed audio. Stream-copy the video when its codec is compatible with the target MP4, and encode only the audio to a broadly compatible MP4 codec:

```bash
ffmpeg -y \
  -i /root/input.mp4 \
  -i /outputs/tts_segments/seg_0.wav \
  -map 0:v:0 -map 1:a:0 \
  -c:v copy \
  -c:a aac -b:a 192k -ar 48000 -ac 1 \
  -t "$SOURCE_DURATION_SEC" \
  -avoid_negative_ts make_zero \
  /outputs/dubbed.mp4
```

Do not use `-shortest` for this delivery: the source duration is authoritative, and the assembled dubbed track must be padded or otherwise prepared to cover that duration. The explicit maps must produce exactly one video stream and exactly one audio stream; no default stream selection is permitted. Do not re-encode the video unless MP4 compatibility requires it, and do not alter its dimensions, pixel format, frame rate, or codec unnecessarily.

3. Verify the mux result before writing the report. Compare source and final format durations, and compare the selected video stream's codec, dimensions, pixel format, frame rate, and duration. Count streams explicitly and reject the output unless it has one intended video stream and one audio stream. Verify that the final audio has sample rate 48000, one channel, a mono layout, and the expected AAC codec. Record and compare the final audio `start_time`; it must use the same zero-based timestamp convention as the prepared timeline rather than being shifted by an unnoticed input offset.

```bash
ffprobe -v error -show_format -show_streams -of json \
  /root/input.mp4 > /outputs/source_mux_probe.json
ffprobe -v error -show_format -show_streams -of json \
  /outputs/dubbed.mp4 > /outputs/final_mux_probe.json

video_count=$(ffprobe -v error -select_streams v \
  -show_entries stream=index -of csv=p=0 /outputs/dubbed.mp4 | sed '/^$/d' | wc -l)
audio_count=$(ffprobe -v error -select_streams a \
  -show_entries stream=index -of csv=p=0 /outputs/dubbed.mp4 | sed '/^$/d' | wc -l)
test "$video_count" -eq 1 && test "$audio_count" -eq 1

ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height,pix_fmt,r_frame_rate,start_time,duration \
  -of json /root/input.mp4
ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height,pix_fmt,r_frame_rate,start_time,duration \
  -of json /outputs/dubbed.mp4
ffprobe -v error -select_streams a:0 \
  -show_entries stream=index,codec_name,sample_rate,channels,channel_layout,start_time,duration \
  -of json /outputs/dubbed.mp4
```

Use the measured final values for `audio_sample_rate_hz`, `audio_channels`, `original_duration_sec`, and `new_duration_sec` in `/outputs/report.json`. Validate the final file and all segment timing checks before declaring the delivery complete; never report planned mux properties as measured values.
