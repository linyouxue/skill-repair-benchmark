# SKILL.md

## When to use
Use this skill when you must **edit a single input video** to remove:
- an **unnecessary opening** (often static/low-value intro), and
- **long pauses / silence segments** (typically those longer than a threshold like ~2s),
while **preserving teaching content** as much as possible, and then produce:
- an edited output video file, and
- a **JSON report** describing durations and the exact removed segments.

Before acting, gather evidence from the target context about:
- **Input path** and required **output filenames/locations**.
- The **minimum pause length** to remove (explicit or implied).
- Any constraints on **runtime** and preferred tooling (e.g., ffmpeg vs Python).
- The required **JSON schema** and any math-consistency requirements.

## Possible Failure Modes
- **Removing too aggressively** (cuts into teaching speech) due to overly high silence threshold, incorrect audio channel selection, or not accounting for low-volume speech.
- **Missing the opening removal** by only using silence detection (openings may include noise/music/static that isn’t “silent”).
- **Incorrect segment timestamps** (off-by-one frame, negative times, end < start, or times outside video duration).
- **Overlapping or unsorted removed segments**, causing concat failures or double-counted removed time.
- **JSON not matching required schema** (missing keys, wrong types, wrong field names, segments missing `duration`).
- **Math inconsistency**: `original_duration_seconds` not approximately equal to `compressed + removed` (floating drift, rounding errors, or miscomputed cut durations).
- **Output artifacts**: A/V desync, glitches at cut boundaries, wrong codecs, or broken container due to improper ffmpeg settings.
- **Slow processing**: full re-encode at high quality or expensive analysis leading to runtime over the limit.
- **Not handling “no segments to remove”**: pipeline crashes or produces invalid/empty outputs instead of a valid pass-through compressed video + correct report.

## Possible procedures
1. **Probe and baseline**
   - Use a media probe tool (e.g., `ffprobe`) to record **duration**, audio presence, sample rate, and stream info.
   - Decide whether to do **stream copy** vs **re-encode** based on cut method (most precise cutting requires re-encode or keyframe-aware strategy).

2. **Detect candidate removal regions**
   - **Silence detection (audio-based)**:
     - Run a silence detector (e.g., ffmpeg `silencedetect`) to get `silence_start` / `silence_end`.
     - Apply a **minimum duration filter** (e.g., keep only pauses longer than threshold).
     - Consider adding small **padding** (e.g., keep 100–300 ms around speech) to avoid clipping words.
   - **Opening detection (structure-based)**:
     - Treat the beginning as a special case: openings may be static/low-motion/low-information.
     - Combine cues: very low motion (optional), lack of speech, repetitive/static frames, or a fixed early-time window.
     - Prefer conservative removal: ensure you don’t cut into the first meaningful teaching segment.

3. **Normalize and consolidate segments**
   - Clip each candidate segment to `[0, original_duration]`.
   - Remove invalid segments (end <= start).
   - **Sort by start time** and **merge overlaps/adjacent gaps** (adjacent within a small epsilon) to avoid double counting.
   - Recompute each segment’s `duration = end - start`.

4. **Construct “keep” timeline and edit**
   - Convert removed segments into a list of **keep segments** (complement intervals).
   - Generate an edit plan compatible with your tooling:
     - For ffmpeg: build a `filter_complex` using `trim`/`atrim` + `concat`, or use the concat demuxer with intermediate segments.
     - Ensure video and audio are cut consistently; reset timestamps (e.g., `setpts/asetpts`) when concatenating.
   - Encode with settings that balance speed and quality (keep runtime constraints in mind). If re-encoding, use common, widely compatible codecs/container settings.

5. **Write the JSON report**
   - Compute:
     - `original_duration_seconds` from probe.
     - `removed_duration_seconds` as sum of merged removed segment durations.
     - `compressed_duration_seconds` as duration of output video (prefer probing output rather than assuming arithmetic).
     - `compression_percentage` as a clearly defined value (e.g., `(removed / original) * 100`), and keep it numeric.
   - Populate `segments_removed` with objects containing numeric `start`, `end`, `duration`.
   - Keep numeric precision consistent (e.g., round to milliseconds) while maintaining math consistency.

6. **Graceful fallback path**
   - If detection yields **no valid segments**, still produce:
     - a valid output video (may be identical or lightly processed), and
     - a valid JSON report with zero removed segments and consistent math.

## Verification Checklist
- **Files present**: required output video and report JSON exist in the expected workspace location with exact required names.
- **Video validity**: output video is playable; has expected streams; no obvious A/V desync; duration is reasonable.
- **Opening removed**: the beginning no longer contains the low-value intro (verify by sampling first ~10–30 seconds).
- **Pause removal quality**: sample around several cut points to confirm long pauses are gone and speech isn’t clipped.
- **Segments sanity**:
  - `segments_removed` sorted by `start`, non-overlapping, within `[0, original_duration_seconds]`.
  - Each segment has `end > start` and `duration ≈ end - start`.
- **JSON schema correctness**: all required top-level keys exist; values are numbers (not strings); `segments_removed` is a list of objects with required keys.
- **Math consistency**:
  - `original_duration_seconds ≈ compressed_duration_seconds + removed_duration_seconds` within a small tolerance.
  - `compression_percentage` matches your documented formula and the other fields.
- **Runtime constraint**: processing completes within the time limit (adjust encode preset / analysis method if not).
- **Non-copying discipline**: do not import any concrete IDs/paths/values from retrieved examples; only apply general tactics (input validation, conservative filtering, schema adherence).
- **Recovery check**: if any probe/edit step fails, re-run with:
  - merged/cleaned segment list,
  - safer padding around speech,
  - or a simpler “no-op” output + correct report rather than producing invalid files.
