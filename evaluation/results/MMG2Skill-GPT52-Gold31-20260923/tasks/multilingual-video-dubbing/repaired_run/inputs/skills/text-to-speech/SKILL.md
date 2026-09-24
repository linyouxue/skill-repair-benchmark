---
name: text-to-speech
description: Produce clean, aligned, delivery-ready TTS segments with loudness normalization,
  boundary cleanup, and export specs for dubbing.
---

## Steps
1. Generate TTS audio per segment using an appropriate engine (neural offline or cloud), then confirm the TTS output’s native sample rate.
2. Clean up each segment (lightweight, consistent chain):
   - High-pass around ~20 Hz (rumble/DC removal)
   - Optional low-pass around ~16 kHz (reduce digital fizz)
   - Add short fades at boundaries (e.g., ~50 ms) to prevent clicks
3. Control duration to fit the timing window:
   - If shorter than the window: **pad silence**
   - If longer: apply gentle **rate_adjust** (small tempo change) or **trim** carefully
4. Loudness workflow (ITU-R BS.1770-4 target behavior):
   - Measure loudness with `ebur128` for reporting/validation.
   - Normalize as a final step with `loudnorm` (e.g., `I=-23`, `TP=-1.5`, `LRA=11`).
   - Do **not** rely on `loudnorm` options that may not exist in the environment (notably `measure_only=1` on some FFmpeg builds); use `ebur128` for measurement and `loudnorm` for normalization.
5. Export delivery audio specs:
   - Ensure output is **48,000 Hz**, **mono**, and a suitable PCM WAV for segment deliverables (e.g., `pcm_s16le`).
## Expected Result
Each TTS segment is clean, click-free, window-aligned with controlled duration (rate_adjust/pad_silence/trim), normalized to a consistent loudness target, and exported as 48 kHz mono audio suitable for muxing into the final dubbed MP4.
