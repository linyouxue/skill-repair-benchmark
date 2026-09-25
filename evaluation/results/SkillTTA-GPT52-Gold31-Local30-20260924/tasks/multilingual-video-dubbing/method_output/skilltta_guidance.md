# SKILL.md

## When to use
Use this skill when you are given:
- An input video file containing the **original visuals** (and possibly original audio),
- Timing constraints for where dubbed speech must occur (e.g., an SRT with segment windows),
- Source transcript text (SRT) and a **target language** indicator,
- A reference target-language script (SRT) to guide what should be spoken,
and you must produce:
1) One or more **TTS segment WAVs** in a required output folder (at least `seg_0.wav`), meeting loudness requirements aligned with **ITU-R BS.1770-4**,
2) A **dubbed MP4** that preserves the original visuals while replacing/adding the new mono 48 kHz audio, with strict timing alignment constraints,
3) A **JSON report** with exact fields (language codes, durations, loudness, per-segment placement/drift, and a controlled vocabulary for duration control decisions).

Before acting, gather evidence by inspecting:
- Segment windows: start/end timestamps (parse SRT precisely to seconds with milliseconds),
- The target language code from the provided file,
- The reference target text per segment (what you will synthesize),
- The input video duration, sample rate/channels of any extracted audio (for comparison), and the required output audio format constraints.

## Possible Failure Modes
- **Mis-parsing SRT times** (e.g., comma vs dot milliseconds, rounding errors) leading to start mismatch > 10 ms or drift > 0.2 s.
- **Using the wrong text source** (e.g., dubbing the source transcript instead of the reference target script, or mismatching segment indices between SRT files).
- **Audio format noncompliance**: output not mono, not 48 kHz, wrong WAV codec/bit depth, or MP4 audio track not matching required format.
- **Loudness noncompliance**: not measuring/normalizing with BS.1770-4-style integrated loudness, causing too quiet/loud “human level” audio or failing evaluator checks.
- **Duration control errors**: TTS exceeds window but not time-compressed; TTS shorter but not padded; trimming that cuts words unnaturally; missing or incorrect `duration_control` label.
- **Muxing mistakes**: altering visuals, changing frame rate unexpectedly, producing a corrupted MP4, or leaving the wrong audio track active.
- **Report/schema drift**: missing required JSON fields, incorrect language codes, wrong numeric types, or values inconsistent with the produced audio/video (durations/LUFS/drift).
- **Overwriting/incorrect paths**: not writing to the exact required output locations or failing to create needed directories.

## Possible procedures
1. **Parse inputs and align segments**
   - Read the segment-window SRT and convert each cue to `window_start_sec` and `window_end_sec` as floating seconds.
   - Read the reference target-text SRT and map text to the same segment ordering/keys. If IDs differ, match by time overlap or nearest timing, not by assuming identical numbering.
   - Capture `target_language` as a short language code string for the report.

2. **Establish timing targets**
   - For each segment: `window_duration_sec = window_end_sec - window_start_sec`.
   - Define acceptance: `|placed_start_sec - window_start_sec| <= 0.010` and `|drift_sec| = |(placed_end_sec - window_end_sec)| <= 0.2`.

3. **Synthesize TTS audio per segment**
   - Generate TTS audio for each segment’s target text (at minimum produce `seg_0.wav` in the required folder).
   - Immediately convert each TTS output to the required working format (48 kHz, mono) to avoid later timing drift from resampling.
   - Measure raw `tts_duration_sec` for each segment.

4. **Fit audio into the time window (duration control decision)**
   - If `tts_duration_sec` is longer than `window_duration_sec`: apply **time compression** (e.g., rate/tempo adjustment) to fit while preserving intelligibility; label as `rate_adjust`.
   - If `tts_duration_sec` is shorter: pad with silence (usually at the end, unless alignment requires otherwise); label as `pad_silence`.
   - If slight overage/underage and quality would suffer from rate change: consider small trims of leading/trailing silence only (avoid cutting phonemes); label as `trim`.
   - Record the chosen control in `duration_control` and recompute final `placed_end_sec` from the adjusted segment duration.

5. **Loudness normalization (BS.1770-4-aligned)**
   - Measure integrated loudness (LUFS) using a BS.1770-4 compatible method (gating-aware integrated loudness).
   - Apply loudness normalization/limiting so the segment(s) are at a consistent “human level” without clipping.
   - Keep this consistent across segments to avoid audible loudness jumps.

6. **Assemble full-length dubbed audio track**
   - Get the input video duration (`original_duration_sec`) using a probe tool (e.g., ffprobe).
   - Build a silent base track of `original_duration_sec` at 48 kHz mono.
   - Mix/overlay each adjusted segment into the base track at exactly `placed_start_sec` (ensure start alignment to within 10 ms by sample-accurate placement).
   - Export the final mix as the audio used for the dubbed MP4 (and keep per-segment WAVs in the segments folder).

7. **Mux dubbed audio with original video**
   - Combine the original video stream (copy) with the newly created mono 48 kHz audio stream.
   - Ensure output duration (`new_duration_sec`) matches the intended timeline (typically the original video duration, unless the contract specifies otherwise).
   - Avoid modifying the visual stream beyond what is necessary for muxing.

8. **Generate the JSON report**
   - Fill required top-level fields: `source_language`, `target_language` (language codes), `audio_sample_rate_hz`, `audio_channels`, `original_duration_sec`, `new_duration_sec`, `measured_lufs`.
   - For each segment: include window times, placed times, texts, computed durations, drift, and `duration_control`.
   - Ensure numeric values reflect **measured** results from produced artifacts, not assumptions.

## Verification Checklist
- [ ] Output files exist at the required paths (segment WAV folder includes at least `seg_0.wav`; dubbed MP4; report JSON).
- [ ] WAV technical compliance: **48,000 Hz**, **mono**, valid PCM WAV; no unexpected re-encoding artifacts.
- [ ] Dubbed MP4 preserves the **original visual stream** (resolution/frames intact) and uses the new mono 48 kHz audio.
- [ ] Timing compliance per segment:
  - [ ] `placed_start_sec` matches the window start within **10 ms**.
  - [ ] `drift_sec = placed_end_sec - window_end_sec` is within **±0.2 s**.
  - [ ] Segment durations in the report match measured audio durations.
- [ ] Loudness compliance:
  - [ ] Integrated loudness measured with a BS.1770-4-compatible method.
  - [ ] `measured_lufs` in JSON matches the produced audio track measurement.
  - [ ] No clipping (peak checks) and consistent perceived loudness across segments.
- [ ] JSON schema correctness:
  - [ ] Language fields are **language codes**, not full names.
  - [ ] All required fields are present with correct types.
  - [ ] `duration_control` is exactly one of: `rate_adjust`, `pad_silence`, `trim`.
- [ ] Consistency checks:
  - [ ] `original_duration_sec` matches probed input video duration.
  - [ ] `new_duration_sec` matches probed dubbed output duration.
  - [ ] `source_text` and `target_text` correspond to the same segment window (no misalignment).
- [ ] Safety/recovery:
  - [ ] If timing is off, re-check SRT parsing (milliseconds) and ensure sample-accurate placement after resampling.
  - [ ] If LUFS is off, redo normalization after final mix (not only per-segment).
- [ ] Non-copying constraint:
  - [ ] Do not import concrete IDs/paths/values from unrelated retrieved examples; only reuse general tactics (strict parsing, exact output formatting, measured-vs-assumed values).
