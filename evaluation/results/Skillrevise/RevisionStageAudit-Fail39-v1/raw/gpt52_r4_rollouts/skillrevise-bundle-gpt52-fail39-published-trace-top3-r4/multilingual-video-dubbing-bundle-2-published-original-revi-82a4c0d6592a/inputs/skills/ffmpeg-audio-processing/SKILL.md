# Verifier-Aligned Segment Dubbing With Contract-Checked JSON Reporting

## Purpose
Create a dubbed audio track from timed text segments, place synthesized speech onto a full-length timeline with precise start placement, mux the new audio with the source video, and emit a JSON report that matches the task's exact verifier contract (key names, types, and metric definitions) using post-write validation gates.

## When to Use
Use this for tasks that require segment-level TTS (or provided speech assets), timing-accurate placement into a single audio track aligned to a source video, plus a machine-checked JSON report that a verifier will parse. Do not use when the task only needs simple audio extraction or a human-readable summary.

## Procedure
- 1) Contract and environment discovery (hard gate before implementation)
- Identify task-declared: input video path, segment specification source, required output paths, and any provided JSON schema or example report.
- If an example report or schema is provided, treat it as authoritative:
- Record exact top-level keys, array names, per-item keys, required/optional fields, and numeric units.
- Record exact definitions for any metrics (for example, what drift_sec measures and its sign convention).
- Tool discovery (no assumptions):
- Confirm ffmpeg and ffprobe are runnable.
- Confirm a writable directory exists for temporary files and task-declared outputs.
- Execution anchor: run ffprobe on the input video and capture duration and audio stream properties.
- Evidence: ffprobe output includes duration and at least one stream listing.
- 2) Parse and validate segment inputs (schema-agnostic, but strict about times)
- Load the segment spec (JSON/CSV/SRT/etc.) and normalize into an internal list with:
- stable id, text, intended_start_sec, and either intended_end_sec or intended_duration_sec
- Validate:
- times are numeric, finite, and non-negative
- end > start when end is provided; duration > 0 when duration is provided
- segment windows fall within media duration unless the task explicitly allows overflow
- Decide overlap policy only from task instructions; if unspecified and overlaps exist, stop and request clarification (do not guess mix/replace behavior).
- 3) Select TTS backend with a micro-test (bounded fallbacks)
- Prefer task-provided or already-installed TTS tools/SDKs; do not perform system-wide upgrades.
- If network TTS is considered, require an explicit connectivity check plus a short synthesis test before committing.
- Execution anchor: synthesize a 1-2 second test phrase to an audio file and verify it exists and is decodable by ffmpeg/ffprobe.
- Evidence: synthesized file is non-empty and ffprobe can read duration.
- 4) Synthesize and normalize per-segment audio assets
- For each segment:
- Generate TTS audio to a temporary file.
- Convert to a single processing invariant discovered from the environment (choose based on source audio when possible): PCM WAV, consistent sample rate, channel count, and sample format.
- Measure actual synthesized duration.
- Handle duration fit using an explicit policy:
- If synthesized duration exceeds the segment window: apply time-stretch only if the required tool is available and the stretch factor stays within safe bounds; otherwise trim with a short fade.
- If synthesized duration is shorter: pad trailing silence to match the intended window if the contract requires window-filling; otherwise leave as-is (must follow task contract).
- 5) Build the full-length dubbed timeline with verifier-defined placement semantics
- Create a silent bed matching the target duration and invariant audio format.
- Place each segment at its intended start time using sample-accurate alignment:
- Compute start_samples = round(intended_start_sec * sample_rate_used)
- Use that exact start_samples for delay/offset so placed_start_sec is derived from the same rounding rule.
- If overlaps are allowed, mix; if overlaps are disallowed, fail fast when detected (unless the task defines a resolution rule).
- Compute placement metadata needed for reporting, but do not name metrics yet until mapped to the contract:
- placed_start_sec, placed_end_sec (from start_samples and segment audio length), and any drift values required by the contract.
- 6) Produce report.json using the discovered contract (no generic defaults)
- Map internal metadata to the exact required output schema:
- Use exact key names from the contract (for example, speech_segments vs segments).
- Only include required fields plus allowed optional fields; do not rename fields to "nicer" names.
- For drift-like fields:
- Implement the exact formula from the contract/example (for example, end drift vs start drift), including sign and units.
- If the contract does not define drift semantics, do not invent a single drift_sec; either:
- ask for clarification, or
- report separate explicitly named fields (for example, start_drift_sec and end_drift_sec) only if the verifier contract allows extra fields.
- 7) Post-write validation gate for report.json (must pass before mux/finalize)
- Execution anchor: reload report.json from the task-declared output path and validate against the discovered contract:
- JSON parses successfully.
- Required top-level keys exist with correct types.
- Required per-segment keys exist with correct types; numeric fields are numbers (not strings) and finite.
- If the contract defines tolerances (for example, max absolute drift), assert them.
- Spot-check drift semantics: recompute the drift formula from placed_* and intended_* fields for a sample of segments and assert equality within a small numeric tolerance.
- If any validation fails, fix the smallest upstream cause (mapping, naming, type casting, or drift formula) and re-run this gate. Do not proceed.
- 8) Mux dubbed audio with the original video and ground outputs
- Mux policy:
- Copy the original video stream without re-encoding when possible (discover stream mapping via ffprobe).
- Add the dubbed audio as the intended primary track; keep or drop original audio only if the task requires it.
- Final grounding checks (against task-declared output paths only):
- Output media file exists, is non-empty, and is readable by ffprobe.
- Output report.json exists at the required path and still passes the validation gate.
- If writing to the required path fails, investigate permissions/mounts and adjust only in ways permitted by the task; do not silently switch to a new path.

## Constraints / Pitfalls
- Do not hard-code report field names (for example, segments) or metric meanings (for example, drift_sec) without first extracting them from the task-provided schema/example; schema mismatches are a primary verifier failure mode.
- Do not claim completion unless (a) report.json reload-and-assert validation passes and (b) final artifacts exist at the exact task-declared output paths and are readable by verifier-visible tools (for example, ffprobe).