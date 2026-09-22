---
name: ffmpeg-audio-processing
description: Extract, normalize, mix, and process audio tracks - audio manipulation and analysis
---

# FFmpeg Audio Processing Skill

Extract, normalize, mix, and process audio tracks from video files.

## When to Use

- Extract audio from video
- Normalize audio levels
- Mix multiple audio tracks
- Convert audio formats
- Extract specific channels
- Adjust audio volume

## Extract Audio

```bash
# Extract as MP3
ffmpeg -i video.mp4 -vn -acodec libmp3lame -q:a 2 audio.mp3

# Extract as AAC (copy, no re-encode)
ffmpeg -i video.mp4 -vn -c:a copy audio.aac

# Extract as WAV (uncompressed)
ffmpeg -i video.mp4 -vn -acodec pcm_s16le audio.wav

# Extract specific audio stream
ffmpeg -i video.mp4 -map 0:a:1 -c:a copy audio2.aac
```

## Normalize Audio

For dubbing, normalize only after every segment has been converted, timed, placed, and mixed into the complete timeline. Do not normalize individual clips and then assume the assembled result has the same loudness. Use a two-pass BS.1770-4 `loudnorm` workflow and remeasure the rendered output.

```bash
# First pass: measure the complete, already assembled timeline.
ffmpeg -hide_banner -nostdin -i /tmp/assembled_dub.wav \
  -af "loudnorm=I=-23:TP=-1.5:LRA=11:print_format=json" \
  -f null - 2> /tmp/loudnorm-pass1.log

# Extract the first-pass values without manually inserting placeholder text.
read INPUT_I INPUT_TP INPUT_LRA INPUT_THRESH TARGET_OFFSET < <(
  python3 - /tmp/loudnorm-pass1.log <<'PY'
import json, re, sys
text = open(sys.argv[1], encoding="utf-8").read()
match = re.search(r'\{\s*"input_i".*?\}', text, re.S)
if not match:
    raise SystemExit("loudnorm JSON was not found")
data = json.loads(match.group(0))
keys = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
print(" ".join(str(data[k]) for k in keys))
PY
)

# Second pass: normalize the whole timeline and preserve its full duration.
ffmpeg -y -hide_banner -nostdin -i /tmp/assembled_dub.wav \
  -af "loudnorm=I=-23:TP=-1.5:LRA=11:measured_I=${INPUT_I}:measured_TP=${INPUT_TP}:measured_LRA=${INPUT_LRA}:measured_thresh=${INPUT_THRESH}:offset=${TARGET_OFFSET}:linear=true:print_format=summary,aresample=48000,aformat=sample_rates=48000:channel_layouts=mono" \
  -ar 48000 -ac 1 -c:a pcm_s16le /outputs/tts_segments/seg_0.wav

# Remeasure the exact file that will be muxed.
ffmpeg -hide_banner -nostdin -i /outputs/tts_segments/seg_0.wav \
  -af "ebur128=framelog=verbose" -f null - 2> /tmp/final-ebur128.log
```

A whole-timeline loudness pass must not be replaced by `volume` or by per-segment normalization. Keep the silent regions in the output; they are part of the timing timeline.

## Volume Adjustment

```bash
# Increase volume by 6dB
ffmpeg -i input.mp4 -af "volume=6dB" output.mp4

# Decrease volume by 3dB
ffmpeg -i input.mp4 -af "volume=-3dB" output.mp4

# Set absolute volume
ffmpeg -i input.mp4 -af "volume=0.5" output.mp4
```

## Channel Operations

```bash
# Extract left channel
ffmpeg -i stereo.mp3 -map_channel 0.0.0 left.mp3

# Extract right channel
ffmpeg -i stereo.mp3 -map_channel 0.0.1 right.mp3

# Convert stereo to mono
ffmpeg -i stereo.mp3 -ac 1 mono.mp3

# Convert mono to stereo
ffmpeg -i mono.mp3 -ac 2 stereo.mp3
```

## Mix Audio Tracks

For multilingual dubbing, assemble a complete silent bed rather than concatenating clips. Parse `/root/segments.srt` as integer milliseconds, and create one fitted 48000 Hz mono WAV per cue at `/outputs/tts_segments/seg_N_fit.wav`. Each fitted clip must already have the cue duration: use a bounded `atempo` rate adjustment when it is too long, append silence when it is short, and trim only as a last resort. Measure the fitted files before placement.

The following executable script creates a full-duration bed and a valid filter graph. It deliberately mixes overlapping speech windows, never truncates the bed because of `adelay`, and writes an unnormalized timeline for the two-pass normalization procedure above:

```bash
cat > /tmp/assemble_dub.py <<'PY'
import json, re, subprocess, sys
from pathlib import Path

srt = Path('/root/segments.srt')
out = Path('/tmp/assembled_dub.wav')
fit_dir = Path('/outputs/tts_segments')

def ms(value):
    h, m, rest = value.replace('.', ',').split(':')
    s, milli = rest.split(',')
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(milli.ljust(3, '0')[:3])

text = srt.read_text(encoding='utf-8-sig')
blocks = re.split(r'\n\s*\n', text.strip())
cues = []
for block in blocks:
    lines = [x.strip() for x in block.splitlines() if x.strip()]
    timing = next((x for x in lines if '-->' in x), None)
    if timing is None:
        continue
    a, b = [x.strip().split()[0] for x in timing.split('-->')]
    cues.append((ms(a), ms(b)))
if not cues:
    raise SystemExit('no SRT cues found')

probe = subprocess.check_output([
    'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
    '-of', 'default=nw=1:nk=1', '/root/input.mp4'], text=True)
duration = float(probe.strip())
subprocess.run([
    'ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono',
    '-t', f'{duration:.6f}', '-ar', '48000', '-ac', '1',
    '-c:a', 'pcm_s16le', '/tmp/dub_bed.wav'], check=True)

cmd = ['ffmpeg', '-y', '-i', '/tmp/dub_bed.wav']
for i, (start, end) in enumerate(cues):
    wav = fit_dir / f'seg_{i}_fit.wav'
    if not wav.exists():
        raise SystemExit(f'missing fitted segment: {wav}')
    cmd += ['-i', str(wav)]

fc = [f'[0:a]atrim=duration={duration:.6f},asetpts=PTS-STARTPTS[bed]']
labels = ['[bed]']
for i, (start, end) in enumerate(cues, 1):
    delay = start
    fc.append(f'[{i}:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=mono,adelay={delay}:all=1[s{i}]')
    labels.append(f'[s{i}]')
fc.append(''.join(labels) + f'amix=inputs={len(labels)}:duration=first:dropout_transition=0,atrim=duration={duration:.6f},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=mono[out]')
cmd += ['-filter_complex', ';'.join(fc), '-map', '[out]', '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', str(out)]
subprocess.run(cmd, check=True)
PY
python3 /tmp/assemble_dub.py
```

The bed is the first `amix` input and has the original media duration, so `duration=first` does not cut delayed speech. Overlaps are intentionally mixed. Do not mix the source audio for a replacement-dub task; map only `[out]`. Preserve source audio only when the task explicitly requests it and document the resulting mix or ducking.

## Audio Delay

Use `adelay` only after converting each speech clip to 48000 Hz mono and fitting it to its SRT window. The delay is an integer millisecond offset from the beginning of the full timeline; it is not a replacement for a full-duration silent bed.

```bash
# One mono clip placed at an exact integer-millisecond offset.
ffmpeg -y -i /outputs/tts_segments/seg_0_fit.wav \
  -af "adelay=500:all=1" -ar 48000 -ac 1 -c:a pcm_s16le /tmp/seg_0_delayed.wav
```

When using `adelay` in a filter graph, mix every delayed clip against a bed whose duration is the desired final duration, then apply `atrim=duration=FINAL_DURATION` to the assembled output. Do not use `-shortest` to decide the final duration: a short delayed input can otherwise truncate the bed, while a long input can extend the result. Measure `placed_start_sec` and `placed_end_sec` from the rendered audio, not from planned offsets.

## Sample Rate Conversion

```bash
# Resample to 48kHz
ffmpeg -i input.mp4 -af "aresample=48000" output.mp4

# Resample audio only
ffmpeg -i input.mp4 -vn -af "aresample=48000" -ar 48000 audio.wav
```

## Audio Filters

```bash
# High-pass filter (remove low frequencies)
ffmpeg -i input.mp4 -af "highpass=f=200" output.mp4

# Low-pass filter (remove high frequencies)
ffmpeg -i input.mp4 -af "lowpass=f=3000" output.mp4

# Band-pass filter
ffmpeg -i input.mp4 -af "bandpass=f=1000:width_type=h:w=500" output.mp4

# Fade in/out
ffmpeg -i input.mp4 -af "afade=t=in:st=0:d=2,afade=t=out:st=8:d=2" output.mp4
```

## Audio Analysis

```bash
# Detect volume levels
ffmpeg -i input.mp4 -af "volumedetect" -f null -

# Measure loudness (LUFS)
ffmpeg -i input.mp4 -af "ebur128=peak=true" -f null -

# Get audio statistics
ffprobe -v error -select_streams a:0 \
  -show_entries stream=sample_rate,channels,bit_rate \
  -of json input.mp4
```

## Combine Multiple Audio Files

```bash
# Concatenate audio files
ffmpeg -i "concat:audio1.mp3|audio2.mp3|audio3.mp3" -c copy output.mp3

# Using file list
# file 'audio1.mp3'
# file 'audio2.mp3'
ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp3
```

## Notes

- Use `-vn` to disable video when extracting audio
- `-map` to select specific streams
- `-af` for audio filters
- `-ac` for channel count
- `-ar` for sample rate
- Normalization may require two passes for accurate results



## Dubbing Delivery and Validation

Mux only the original video stream and the assembled, normalized dub. Do not use `-shortest`; explicitly control the final duration with `-t` from the source media duration.

```bash
DURATION_SEC=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 /root/input.mp4)
ffmpeg -y -i /root/input.mp4 -i /outputs/tts_segments/seg_0.wav \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -ar 48000 -ac 1 \
  -t "$DURATION_SEC" /outputs/dubbed.mp4

ffprobe -v error -select_streams a:0 \
  -show_entries stream=sample_rate,channels,channel_layout,duration \
  -of json /outputs/tts_segments/seg_0.wav
ffprobe -v error -select_streams a:0 \
  -show_entries stream=sample_rate,channels,channel_layout,duration \
  -of json /outputs/dubbed.mp4
```

Before writing `/outputs/report.json`, verify that the final file has one intended audio stream, 48000 Hz, mono, and the original video stream. Parse SRT timestamps as integer milliseconds and measure each rendered segment's first and last non-silent samples. Report `placed_start_sec`, `placed_end_sec`, and `drift_sec = placed_end_sec - window_end_sec` from those measurements; do not copy planned offsets into the report. Require `abs(placed_start_sec - window_start_sec) <= 0.010` and `abs(drift_sec) <= 0.200` for every cue. Use the source and target transcript text exactly as supplied, and use language codes from the input files rather than inventing them. Record `duration_control` only as `rate_adjust`, `pad_silence`, or `trim`, and record `measured_lufs` from the final rendered file's BS.1770-compatible measurement.
