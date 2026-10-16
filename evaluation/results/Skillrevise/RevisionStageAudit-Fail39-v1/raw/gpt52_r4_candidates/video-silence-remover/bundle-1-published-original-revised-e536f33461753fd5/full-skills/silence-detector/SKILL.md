# Pause-and-Silence Remover (Media)

## Purpose
Detect long pauses/silence throughout an audio/video file, remove those intervals, and produce an edited media file plus a machine-readable report, with verifier-aligned output checks.

## When to Use
Use when a task requires finding pauses/silent gaps across the full timeline (not just the beginning), removing intervals longer than a specified minimum duration, and emitting explicit output artifacts (edited media and a JSON report) at paths named in the task instructions.

## Procedure
- Step 1: Preflight (inputs, outputs, tools, assumptions)
- Read the task instructions and extract: input media path, required output media path, required report path, and the minimum pause duration threshold (if unspecified, stop and request clarification rather than guessing).
- Validate input media path: exists, is a regular file, readable, and non-zero size.
- Discover tools (do not assume fixed install locations):
- Prefer `ffmpeg` and `ffprobe` if available (`command -v ffmpeg`, `command -v ffprobe`).
- If missing, stop and request an alternative tool allowance rather than inventing commands.
- Execution anchor: run `ffprobe` to record baseline duration and confirm decodability; keep the measured duration for later bounds checks.
- Step 2: Detect candidate pause segments across the entire timeline (choose a method, then normalize)
- Primary method (preferred when available): ffmpeg `silencedetect` on the audio track to find silence start/end events.
- Run detection to produce a plain-text log (to a temp file in the working directory) and parse it into segments.
- Fallback method: if `silencedetect` is unavailable or produces no usable events, use an energy-based approach (frame/window energy with smoothing) only if the needed dependencies are present; otherwise stop and request guidance.
- Normalize segments:
- Convert detection events into `[start, end]` intervals in seconds.
- Clamp to `[0, media_duration]`.
- Drop intervals with `end <= start`.
- Apply the task-defined minimum duration threshold (keep only intervals with duration >= threshold).
- Optionally merge intervals separated by a very small gap only if the task specifies merge behavior; otherwise do not merge.
- Checkpoint: if zero segments remain, do not silently fail; proceed with a no-op edit plan (copy/remux original) but still generate a valid report stating that no pauses above threshold were found.
- Step 3: Build a safe cut plan and produce the edited media
- Construct the keep-intervals as the complement of the removed segments over `[0, duration]`.
- Validate the plan before editing:
- Keep-intervals must be sorted, non-overlapping, within bounds, and have positive durations.
- Total kept duration should be `original_duration - total_removed_duration` within a small tolerance (to account for timestamp rounding).
- Render edited output using a method appropriate to the environment and requirements:
- Prefer a concat-based workflow that trims and concatenates keep-intervals in timeline order.
- Choose stream copy vs re-encode based on task constraints; if not specified, prefer a safe default that produces a broadly playable file (but do not claim lossless behavior).
- Write output to the exact required output media path from the task (do not redirect to a different directory if it fails).
- Step 4: Write the report JSON and verify outputs (must pass observable checks)
- Create a report JSON that (at minimum) includes:
- `method` (string), `parameters` (object including min_pause_duration and detection settings used),
- `removed_segments` (list of objects with numeric `start`, `end`, `duration`),
- `totals` (object with total_removed_duration_seconds, original_duration_seconds, output_duration_seconds).
- If the task specifies an exact schema/field names, follow that schema instead of this minimal one.
- Post-write validation (schema + bounds):
- Reload the JSON from disk and validate required keys/types.
- Assert every segment is within `[0, original_duration]` and `duration == end - start` within tolerance.
- Execution anchor: final verifier-aligned checks at the exact task-specified output paths:
- Output media file exists, is readable, and size > 0.
- `ffprobe` can decode the output media (non-error exit).
- Report file exists, is readable, and parses as valid JSON.
- If any check fails, do not switch paths silently; instead diagnose: permissions, missing mounts, wrong output path extracted from instructions, or ffmpeg failure logs.

## Constraints / Pitfalls
- Never hard-code absolute script paths, repo-internal locations, or assume auxiliary skills exist; always discover available tools and operate from task-provided input/output paths.
- Do not remove or cut media until (a) input decodes via ffprobe, (b) pause threshold is confirmed from instructions, and (c) segments are normalized and validated to be in-bounds and non-overlapping; otherwise you risk corrupt outputs or removing content incorrectly.