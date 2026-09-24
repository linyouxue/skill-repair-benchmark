# NPZ Waveform Phase Picking to Verifier-Aligned CSV

## Purpose
Provide a reusable, discovery-first workflow to generate seismic phase picks (for example P and S) from NPZ waveform inputs using an available picker (prefer SeisBench when installed), convert picks to sample indices aligned to the original waveform, and write a verifier-ready CSV with post-write schema checks.

## When to Use
Use when a task provides waveform data in NPZ (or similarly structured arrays) and requires producing a CSV of phase picks (often as sample indices, optionally with times and scores). Do not use for ObsPy file-format tutorials, event catalogs, or station metadata handling unless the task explicitly requires those.

## Procedure
- Step 1: Discover requirements and environment before any heavy compute or writes.
- Identify the required output path from the task instructions. If not explicitly given, stop and request/locate it (for example, search the working directory for a required filename pattern); do not silently choose a new path.
- Check tool availability: in Python, attempt imports in this order and record which path is usable:
- `seisbench` (preferred for pretrained pickers)
- `obspy` (only for wrapping arrays into Trace/Stream if needed)
- pure NumPy/SciPy fallback (peak-picking on provided probabilities, if any)
- Execution anchor (evidence): print versions for imported libs and the resolved output path.
- Step 2: Load NPZ and validate input schema (discovery-first).
- Load with `numpy.load(..., allow_pickle=True)` and list keys.
- Determine the waveform array key by inspection (common candidates: `data`, `X`, `waveform`, `waveforms`). Do not assume a fixed key until verified.
- Determine sampling metadata:
- Prefer `dt` if present; else `sampling_rate`/`fs`; else infer from a time vector if present; else fail with a clear request.
- Validate invariants needed for picking:
- Waveform must be numeric, finite (no all-NaN), and have a clear time axis.
- Determine shape convention by inspection: (n_samples, n_channels) vs (n_channels, n_samples) vs batched. Normalize to a single 2D array (n_channels, n_samples) for downstream processing.
- Determine channel names if present (common keys: `channels`, `channel_names`). If missing, create placeholders but mark that channel semantics are unknown.
- Checkpoint: print a concise input report: keys, normalized shape, n_samples, n_channels, dt, derived sampling_rate, and channel labels.
- Step 3: Preprocess conservatively and run picker using the best available method.
- Preprocessing (only if needed for the chosen model):
- Detrend / demean per channel.
- Optional normalization to unit variance per channel, but do not clip or resample unless the model requires it and you have verified the model expectation.
- Picker decision:
- If SeisBench is available: select an appropriate pretrained picker model available in the environment (discover by listing model registry / attempting common pickers). Do not hard-code a single model name without checking availability.
- If a model requires a specific sampling rate, prefer resampling only after validating the target rate and recording the mapping back to original indices.
- If SeisBench is not available: if probability traces are already provided in the NPZ, peak-pick those; otherwise fail with a clear message that a picker/model is missing.
- Run inference to obtain pick times or per-sample probabilities for phases.
- Checkpoint: store raw outputs (times/probabilities and any metadata such as starttime/blinding).
- Step 4: Align model outputs to the original waveform index space (no silent offsets).
- Compute alignment facts:
- `npts_in = n_samples_original`.
- Determine `npts_out` for each output series (probabilities/annotations).
- If `npts_out != npts_in`, infer whether this is due to model blinding/cropping/padding:
- Look for explicit metadata (for example, starttime offset, valid window start/end, or known model "blind" seconds) exposed by the library.
- If metadata is missing, do not guess a constant. Instead, compute candidate offsets by comparing known features (for example, cross-correlate an energy envelope with output peaks) only if justified; otherwise stop and surface ambiguity.
- Convert to indices:
- If you have pick times: `idx = round((t_pick - t0_original) * sampling_rate)` with any validated offset applied.
- If you have probabilities: choose peaks per phase with a configurable threshold and minimum separation; convert peak sample positions to original indices using the validated mapping.
- Execution anchor (evidence): print an alignment report and assert bounds:
- Report `npts_in`, `npts_out`, inferred offset in seconds and samples (or "none"), and min/max pick index per phase.
- Assert every emitted pick index is an integer and in `[0, npts_in - 1]`. If the assertion fails, do not write the final CSV; instead, revisit alignment or lower-level outputs.
- Step 5: Build the results table and write CSV to the required path, then reload and validate.
- Determine the required CSV schema from the task. If not explicitly specified, derive a minimal schema that is consistent and self-describing, and clearly document it in logs; however, prefer the task-declared schema whenever available.
- Populate rows with at least:
- a stable record identifier (for example, file id or trace id) if the task indicates multiple records
- phase label (for example, "P", "S")
- pick index (integer sample index in the original waveform)
- optional: pick time (seconds) and score/probability
- Write CSV with a standard dialect (comma-separated, header row, UTF-8 is fine but content must be printable ASCII where possible).
- Execution anchor (evidence): reload and validate the written CSV:
- Confirm the file exists and is readable at the exact required path.
- Reload with `csv`/`pandas` and assert: required columns exist, pick index column parses to integers, and all indices are within bounds.
- Print a final summary: path, row count, column names.

## Constraints / Pitfalls
- Do not assume NPZ keys, waveform axis order, channel naming, model name, sampling rate, or a fixed offset/blinding constant. Always discover and validate; if alignment cannot be proven, stop rather than emitting likely-wrong indices.
- Do not write outputs to an arbitrary path. Use only the task-specified output path; if it is missing or unwritable, diagnose permissions/mounts and fail clearly instead of silently redirecting.