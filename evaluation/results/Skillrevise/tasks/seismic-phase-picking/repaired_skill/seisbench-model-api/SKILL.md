# SeisBench NPZ-to-Picks Pipeline (Annotate to Discrete P/S Indices)

## Purpose
Provide a reusable, verifier-oriented workflow to load waveform data from NPZ-like arrays, run a SeisBench pretrained picking model, extract discrete P and S picks using explicit peak/threshold rules, and write a validated prediction table (typically CSV) with pick indices (or times if required).

## When to Use
Use this skill when the task requires converting waveform arrays (commonly NPZ/NumPy) into discrete seismic phase picks (P and/or S) using SeisBench pretrained models, and the deliverable is a machine-readable table of picks per record. Do not use if the task is about training models, non-picking tasks (magnitude, localization), or if the task specifies a different framework/output format that cannot be produced by a simple pick-index table.

## Procedure
- Step 0: Confirm the observable contract (before coding)
- Read the task prompt for: required output file path/name, required columns, whether picks are sample indices vs seconds, whether multiple picks per trace are allowed, and how missing picks must be encoded.
- If a sample submission or evaluation script is present, inspect it to extract exact schema and units. If not present, treat schema as ambiguous and keep output flexible but validated.
- Step 1: Discover the input layout (execution anchor)
- List available input files and choose one representative NPZ to inspect.
- Load it and enumerate keys, shapes, and dtypes. Identify:
- The waveform array key(s) and expected shape convention (for example: [n_samples], [n_channels, n_samples], [n_traces, n_samples], etc.).
- Any metadata fields (sampling rate, start time, station/channel ids, record ids).
- Decision point:
- If sampling rate is not present in data/metadata, stop and search for it in accompanying docs/config; do not assume a fixed rate.
- Step 2: Validate and normalize waveforms (no irreversible actions)
- For each record/trace to be picked:
- Assert finite values (no NaN/Inf). If present, replace with zeros or interpolate only if the task allows; otherwise drop the record and log.
- Detrend/demean each trace (at minimum remove mean).
- Detect extreme scaling issues: if max(abs(x)) is extremely small relative to float precision, scale by a constant factor only after confirming it improves numerical stability (keep the factor recorded for debugging).
- Checkpoint evidence:
- Log per-record n_samples, sampling_rate, and amplitude summary (min/max/std) after preprocessing.
- Step 3: Build an ObsPy Stream with correct stats (grounded in discovery)
- Convert each waveform to one or more ObsPy Trace objects with:
- stats.sampling_rate from discovered metadata,
- stats.starttime if available (otherwise a consistent placeholder is acceptable only if outputs are indices, not absolute times),
- stats.network/station/location/channel when present (or stable placeholders if grouping is not required).
- Decision point:
- If the model expects a specific sampling rate, either resample explicitly (and log method) or reject the record; do not silently rely on implicit resampling unless verified in this environment.
- Step 4: Load and run a pretrained SeisBench picking model (discover, then act)
- Import seisbench.models and list available pretrained variants for the intended model class (for example PhaseNet or EQTransformer).
- Load a pretrained weights set only after confirming it is available; if download fails (offline/no cache), fall back to:
- another available pretrained variant, or
- a local cached model path if the environment provides one,
- otherwise fail fast with a clear error.
- Run model.annotate(stream) to get continuous probability traces (preferred for explicit peak finding).
- Checkpoint evidence:
- Confirm annotation stream exists and has expected components (P and S probability traces or model-specific labels).
- Confirm annotation trace lengths align with the input time base (or record any fixed offset/stride if present).
- Step 5: Convert probabilities to discrete picks (explicit decision rules)
- For each phase probability series (P and S):
- Smooth lightly only if needed (and deterministic), then find candidate peaks using:
- a threshold (relative, such as a fraction of that trace max, and/or absolute, if supported by task calibration),
- a minimum peak distance in samples derived from sampling_rate and a minimum separation in seconds.
- Select picks using a rule that matches the task requirement:
- If exactly one pick per phase is required: choose the highest peak above threshold.
- If multiple picks allowed: output all peaks above threshold with ordering by time.
- Enforce phase ordering only as a soft constraint:
- If both P and S exist and S must be after P, filter S candidates to those after the chosen P; if none remain, either mark S missing or keep best S depending on task instructions.
- Always output pick locations in the required unit:
- If sample indices: convert from time to integer sample index via round((t - t0) * sampling_rate) using the same t0 used for stream construction.
- If seconds: output relative seconds from record start unless absolute time is explicitly required.
- Hard bounds check:
- Clamp is not allowed; instead, treat out-of-range picks as invalid and set them to missing, and log the count.
- Step 6: Write outputs and validate schema (execution anchor)
- Write the table to the required path/filename.
- Immediately reload the written file and assert:
- Row count matches number of input records required by the prompt.
- Required columns exist and types are parseable.
- For each record, any non-missing pick index is an integer and satisfies 0 <= idx < n_samples for that record.
- If any assertion fails, do not submit; instead, fix the upstream mapping (units, indexing, row ordering, missing encoding) and re-run.

## Constraints / Pitfalls
- Do not hard-code sampling rate, NPZ keys, waveform shape conventions, output column names, or output file paths unless they are explicitly verified from the task prompt or discovered artifacts (for example sample submission). Always discover first.
- Avoid brittle pick heuristics like global argmax without thresholds/peak separation and without validating alignment/units; such heuristics often produce plausible-looking outputs that fail the verifier.