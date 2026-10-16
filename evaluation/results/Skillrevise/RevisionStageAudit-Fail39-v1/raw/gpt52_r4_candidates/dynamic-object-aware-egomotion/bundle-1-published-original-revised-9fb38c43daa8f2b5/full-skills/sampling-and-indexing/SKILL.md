# Sampling And Index-Domain Alignment

## Purpose
Standardize video sampling while explicitly separating sampled-frame indices from source-video frame indices, so interval instructions and per-frame artifacts align with the verifier-expected index domain and any task-specified sampling rate.

## When to Use
Use when a task requires sampling a video at a specified rate (for example, 5 fps) and producing downstream artifacts (JSON intervals, masks, frame arrays) that must be indexed consistently and validated against a schema/contract.

## Procedure
- 1) Discover inputs and requirements (do not assume):
- Locate the video input(s) and the required outputs from the task instructions (paths, formats, naming).
- Extract source metadata with an available tool (preferred: ffprobe; fallback: OpenCV): total frames N (or duration), source fps src_fps, and duration.
- Determine whether the task specifies required_fps (or a stride). If required_fps is specified, treat it as mandatory.
- 2) Define and name the two index spaces up front:
- sample_i: integer index into the sampled sequence, range [0, S-1].
- src_frame: integer index into the original video frames, range [0, N-1] (if N known).
- Decide a deterministic mapping rule from sample_i to src_frame (or to timestamp), and write it down as part of your run notes (for example: sample at uniform times t = k/required_fps; convert to src_frame via a single rounding rule; clamp to valid range; then deduplicate while preserving order).
- 3) Generate the sampling mapping (mandatory when required_fps is given):
- If required_fps is given:
- Compute sample times across the full duration using that rate.
- Convert each sample time to a src_frame using your chosen rounding rule and clamp to [0, N-1] when N is known.
- If required_fps is not given:
- Choose a strategy based on discovered src_fps and task goals; record the chosen policy explicitly.
- Create an ordered mapping array/map: map_sample_to_src where len(map_sample_to_src) = S and each entry is a src_frame (or equivalent source locator).
- Checkpoint: assert mapping is strictly increasing (or non-decreasing only if you explicitly allow and then remove duplicates), and all mapped src_frame values are within bounds when N is known.
- 4) Produce downstream artifacts strictly in sample_i space:
- All interval keys in JSON must use sample_i endpoints only, not src_frame.
- Key format must be exactly "start->end" where start and end are base-10 integers.
- Use a single, consistent interval convention: end is exclusive (recommended) so each interval covers sample_i in [start, end).
- Any per-frame artifact store (NPZ/arrays/images) must contain exactly S frames in sample_i order (frame 0 corresponds to sample_i=0, etc.).
- If any consumer needs src_frame, include it as separate data (for example, a sidecar mapping JSON) rather than overloading interval keys.
- 5) Post-write contract validation (before claiming completion):
- Reload written artifacts from disk.
- Infer S from the per-frame artifact store length (or from mapping length), and validate:
- Interval key schema: every key matches "digits->digits"; parsed start/end are integers.
- Domain: for all intervals, 0 <= start < end <= S.
- Coverage: max(end) equals S (when full coverage is required) and there are no references to indices >= S.
- Per-frame store length equals S exactly.
- Mapping validity: map_sample_to_src length equals S; values monotone; values within [0, N-1] when N known.
- If any check fails: stop, identify whether the error is (a) wrong index domain, (b) wrong S, (c) wrong sampling cadence, or (d) tool/metadata issue; then regenerate mapping and downstream artifacts accordingly.

## Constraints / Pitfalls
- Never mix index domains: JSON interval endpoints must be sample_i unless the task explicitly says otherwise; do not use src_frame numbers as interval keys.
- If required_fps (or stride) is specified by the task, sampling is not a free choice. Enforce it and validate cadence via the mapping; do not silently substitute a "reasonable" fps/step.
- Do not take irreversible actions (overwriting outputs) until discovery is complete and you have a validated mapping; always run the post-write reload-and-assert checks.
- If the preferred metadata tool is missing or returns unknown values, use a fallback tool and, if duration/N cannot be reliably determined, require clarification or constrain behavior (for example, sample based on decoded frames and stop at end-of-stream) and document that choice.