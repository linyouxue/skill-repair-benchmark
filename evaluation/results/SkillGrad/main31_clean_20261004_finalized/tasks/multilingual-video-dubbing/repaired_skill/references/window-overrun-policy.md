# Policy for segment/window overruns (window end beyond source duration)

Use this when a required segment window extends past the available source media duration.

## Step 1) Measure actual source duration

```bash
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 input_video.ext
```

## Step 2) Choose a policy (branch)

Runtime branch:

### Branch A — Pad/extend the output to honor the window (preferred when windows are “hard”)

- Extend **video** to the required end time by freezing the last frame (or adding black frames).
- Extend **audio** with silence to the same end time.
- Keep the report window times unchanged; your placed media reaches them.

```bash
# Extend video by freezing last frame to a target duration
ffmpeg -i input_video.ext -vf "tpad=stop_mode=clone:stop_duration=1" -c:v libx264 -an video_extended.mp4

# Extend audio to target duration with silence
ffmpeg -i input_audio.ext -af "apad" -t 1 output_audio_padded.wav
```

### Branch B — Clamp to source duration and make the report consistent (only when allowed)

- Do not extend media.
- Clamp placement end to source duration.
- Update any report fields so that `window_end` and `placed_end` are consistent with the chosen rule (and compute drift against the clamped window, not the original).

```python
# Example: enforce internal consistency between window and placement when clamping
source_dur = 0.0
window_start, window_end = 0.0, 0.0
placed_start = window_start
placed_end = min(window_end, source_dur)
window_end_effective = placed_end
assert window_end_effective == placed_end
```

## Step 3) Verification + corrective action

Verification:
1. Re-probe the **final output** duration.
2. Check that the report fields match the chosen policy (no “window_end beyond duration” without an explicit rule).

```bash
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 output_video.ext
```

If verification fails:
- If the output duration is still shorter than required, increase the pad/extend duration and re-render.
- If the report is inconsistent, regenerate the report from the same timestamps used to build the media (single source of truth).
