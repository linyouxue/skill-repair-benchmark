---
name: ffmpeg-media-info
description: Analyze media file properties - duration, resolution, bitrate, codecs, and stream information
---

# FFmpeg Media Info Skill

Extract and analyze media file metadata using ffprobe and ffmpeg.

## When to Use

- Get video/audio file properties
- Check codec information
- Verify resolution and bitrate
- Analyze stream details
- Debug media file issues

## Basic Info Commands

```bash
# Show all file info
ffmpeg -i input.mp4

# JSON format (detailed)
ffprobe -v quiet -print_format json -show_format -show_streams input.mp4

# Simple format
ffprobe -v quiet -print_format json -show_format input.mp4
```

## Duration

```bash
# Get duration in seconds
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 input.mp4

# Duration with timestamp format
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 -sexagesimal input.mp4
```

## Resolution

```bash
# Get video resolution
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height \
  -of csv=s=x:p=0 input.mp4

# Get resolution as JSON
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height \
  -of json input.mp4
```

## Bitrate

```bash
# Get overall bitrate
ffprobe -v error -show_entries format=bit_rate \
  -of default=noprint_wrappers=1:nokey=1 input.mp4

# Get video bitrate
ffprobe -v error -select_streams v:0 \
  -show_entries stream=bit_rate \
  -of default=noprint_wrappers=1:nokey=1 input.mp4
```

## Codec Information

```bash
# Video codec
ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,codec_long_name \
  -of default=noprint_wrappers=1 input.mp4

# Audio codec
ffprobe -v error -select_streams a:0 \
  -show_entries stream=codec_name,codec_long_name \
  -of default=noprint_wrappers=1 input.mp4
```

## Sample Rate and Channels

```bash
# Audio sample rate
ffprobe -v error -select_streams a:0 \
  -show_entries stream=sample_rate \
  -of default=noprint_wrappers=1:nokey=1 input.mp4

# Audio channels
ffprobe -v error -select_streams a:0 \
  -show_entries stream=channels \
  -of default=noprint_wrappers=1:nokey=1 input.mp4
```

## Stream Count

```bash
# Count video streams
ffprobe -v error -select_streams v -show_entries stream=index \
  -of csv=p=0 input.mp4 | wc -l

# Count audio streams
ffprobe -v error -select_streams a -show_entries stream=index \
  -of csv=p=0 input.mp4 | wc -l
```

## Frame Rate

```bash
# Get frame rate
ffprobe -v error -select_streams v:0 \
  -show_entries stream=r_frame_rate \
  -of default=noprint_wrappers=1:nokey=1 input.mp4
```

## Notes

- Use `-v error` to suppress warnings
- `-of json` for structured output
- `-select_streams` to target specific streams (v:0 for first video, a:0 for first audio)


## Deterministic Multilingual Dubbing Validation Contract

For multilingual dubbing, validation is a required machine-readable stage, not an informational postscript. Do not create `/outputs/report.json` until every required file and every validation below passes. Any missing file, malformed JSON, missing field, failed comparison, timing violation, or loudness-measurement failure must terminate the workflow with a nonzero status and must not leave a misleading report.

### Probe all artifacts as JSON

Probe the source video, every generated segment WAV, the assembled full-duration WAV, and the muxed MP4. Save the exact probe output so validation is reproducible:

```bash
set -eu
mkdir -p /outputs/qa
probe() {
  test -s "$1"
  ffprobe -v error -print_format json -show_format -show_streams "$1" > "$2"
}
probe /root/input.mp4 /outputs/qa/source.ffprobe.json
for f in /outputs/tts_segments/*.wav; do
  probe "$f" "/outputs/qa/$(basename "$f").ffprobe.json"
done
probe /outputs/assembled.wav /outputs/qa/assembled.ffprobe.json
probe /outputs/dubbed.mp4 /outputs/qa/dubbed.ffprobe.json
```

The validator must parse these JSON files rather than scrape human-readable ffprobe output. For each file retain `format.duration`, `format.start_time`, stream `index`, `codec_type`, `codec_name`, `codec_long_name`, `start_time`, and `duration`; retain video `width`, `height`, `pix_fmt`, and `r_frame_rate`; and retain audio `sample_rate`, `channels`, and `channel_layout`. Fail on absent or nonnumeric values instead of silently substituting zero.

### Validate source preservation and final streams

Compare the source video stream (`v:0`) with the muxed video stream (`v:0`). The final must preserve the source visual stream: require the same video codec, width, height, pixel format, frame-rate value, and stream-level start time, and require a final duration equal to the source duration within the container time-base measurement tolerance. Do not re-encode the visual stream merely to satisfy QA. Record both source and final codec properties in the QA data.

The muxed MP4 must contain exactly one audio stream and that stream must be the intended assembled dub, not an accidentally retained source track. Require one `codec_type=audio` stream, a valid codec, `sample_rate=48000`, `channels=1`, and a single-channel layout such as `mono`. Validate its `start_time`, `duration`, and codec properties against the assembled WAV and verify that the audio is not truncated relative to the required full video timeline. Also validate that every segment WAV and the assembled WAV are readable, have `sample_rate=48000`, one channel, a valid start time, and a measurable duration.

### Parse SRT timestamps without rounding

Parse `/root/segments.srt`, `/root/source_text.srt`, and `/root/reference_target_text.srt` with one parser. Accept both comma and period millisecond separators, convert each timestamp directly to an integer count of milliseconds, and retain the original cue order and cue indices. Calculate seconds only as `milliseconds / 1000` for reporting; never round, truncate, or reconstruct a placement from displayed decimal seconds. Require matching cue entries for the segment window, source transcript, and target transcript. Preserve the supplied source and target text exactly (apart from the parser's documented newline normalization); never invent missing text.

For every segment, calculate and retain:

- `window_start_sec` and `window_end_sec` from the integer SRT millisecond values;
- `window_duration_sec = (end_ms - start_ms) / 1000`;
- `tts_duration_sec` from the corresponding rendered segment WAV using its probed duration;
- `placed_start_sec` and `placed_end_sec` from the actual assembled/rendered audio timeline, measured in samples or an equivalent unrounded timebase rather than copied from the planned window;
- `drift_sec = placed_end_sec - window_end_sec`;
- the supplied `source_text` and `target_text`; and
- `duration_control`, which must be exactly `rate_adjust`, `pad_silence`, or `trim`.

Use one deterministic non-silence threshold and the same sample-level measurement procedure for every cue. Measure the rendered assembled WAV (and, where necessary, confirm the same positions in the muxed MP4); do not infer actual placement merely from an `adelay` argument. Validate `abs(placed_start_sec - window_start_sec) <= 0.010` and `abs(drift_sec) <= 0.200` for every cue. Validate that the assembled audio begins at the required timeline origin and covers the source video duration without an unreported leading offset or truncation.

### Validate loudness and report inputs

Measure the final intended audio stream, preferably the exact WAV mapped into the MP4, with an ITU-R BS.1770-compatible filter. Capture machine-readable output from `loudnorm` or the integrated result from `ebur128`, and use the measured integrated loudness—not peak, RMS, or a nominal target—as `measured_lufs`:

```bash
ffmpeg -hide_banner -v error -i /outputs/tts_segments/seg_0.wav \
  -af 'loudnorm=I=-23:TP=-1.5:LRA=11:print_format=json' \
  -f null - 2> /outputs/qa/final-loudness.json
```

Fail if the filter does not produce a finite integrated loudness value. Confirm that `/outputs/tts_segments/seg_0.wav` is the complete final audio used for muxing, not an intermediate segment or a separately modified copy. Validate the report schema before writing the report: require `source_language` and `target_language` to be nonempty language codes obtained from supplied metadata/files, require the target value to come from `/root/target_language.txt`, and fail rather than guessing a language code. Require every `speech_segments` entry and all timing, duration, text, control, audio-format, duration, and loudness fields listed by the task. `original_duration_sec` must come from the source probe and `new_duration_sec` from the muxed MP4 probe.

Only after all probes, source/video comparisons, stream-count checks, format checks, exact-timestamp checks, rendered timing tolerances, loudness checks, language/text provenance checks, and JSON-schema checks pass may the validator serialize `/outputs/report.json`. Re-open the written file, parse it as JSON, and repeat the required-field and tolerance checks before declaring success.
