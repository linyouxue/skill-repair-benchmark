# Silence-Based Video Compression

## Purpose
Produce a shorter video by detecting and removing silent segments (both leading silence and internal pauses above a task-specified threshold), then emit a compression report that documents what was removed. The skill covers the full detect -> cut -> report pipeline, not just detection.

## When to Use
Trigger when the task requires compressing or trimming an audio/video file by removing silent regions and emitting an output video plus a structured compression report. Do not fire for pure transcription, pure silence annotation without cutting, or tasks that forbid re-encoding.

## Procedure
- Discover inputs and contract: locate the input media file from the task description; read the task to extract required output paths (e.g., compressed video, report JSON), the minimum pause duration to remove (default 2.0s if unspecified), and any schema keys the report must contain. If paths are not given, write outputs beside the input using descriptive names and record the choice.
- Measure baseline: run `ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 <input>` to capture `original_duration_seconds`. Confirm `ffmpeg` and `ffprobe` are available with `which ffmpeg ffprobe`; if missing, stop and report the environment gap instead of silently switching tools.
- Detect silence segments across the entire file (not only the opening):
- Primary method: `ffmpeg -i <input> -af silencedetect=noise=-30dB:d=<min_pause> -f null - 2>&1` and parse `silence_start` / `silence_end` lines into `[{start, end, duration}]`.
- Fallback method: if an energy-based detector is already available in the environment (discover via `find` or project README; do not assume a fixed path), compute per-frame energy, apply a moving-average smoothing, and threshold against a baseline multiplier. Use this when `silencedetect` is unavailable or produces zero segments on known-silent regions.
- Tune `noise` dB and `min_pause` only if the first pass yields obviously wrong results (e.g., zero segments in a long recording); never return an empty segments list without retrying.
- Build the keep-timeline: invert the silence segments into keep-intervals over [0, original_duration]. Merge adjacent keep-intervals separated by less than ~0.1s to avoid tiny cuts.
- Cut and concatenate with ffmpeg: for each keep-interval, create a trimmed clip using `-ss <start> -to <end> -c copy` when stream-copy is safe, otherwise re-encode. Concatenate via the concat demuxer (`ffmpeg -f concat -safe 0 -i list.txt -c copy <output>`); fall back to filter_complex concat with re-encoding if stream-copy fails. Write to the task-specified output path.
- Emit the compression report as JSON with exactly the keys required by the task; if unspecified, use: `original_duration_seconds`, `compressed_duration_seconds`, `removed_duration_seconds`, `compression_percentage`, `segments_removed` (list of `{start, end, duration}`). Compute `compressed_duration_seconds` by running `ffprobe` on the output, not by arithmetic alone.
- Post-write validation (mandatory execution anchor): reload the report JSON and assert all required keys exist and types are numeric/list as expected; assert `abs(original - compressed - removed) < 0.5` seconds; `ls -l` both output artifacts to confirm existence and non-zero size. If any assertion fails, repair before claiming completion.

## Constraints / Pitfalls
- Do not hard-code paths to sibling skills or scripts; discover tools and helpers at runtime and fall back to direct `ffmpeg`/`ffprobe` when sibling utilities are absent.
- Do not scope detection to the opening of the file; internal pauses meeting the threshold must also be removed.
- Do not invent report keys beyond what the task specifies; match the requested schema exactly, and do not drop required keys.
- Never finalize with an empty `segments_removed` list unless detection genuinely found none after at least one retry with adjusted parameters; log the retry.
- Prefer stream-copy for speed, but re-encode when codecs, timestamps, or keyframe alignment make stream-copy unsafe; verify the output is playable via `ffprobe` before validation.
- Write outputs to the exact task-specified paths; if writing fails, inspect permissions and mounts rather than silently relocating the artifact.