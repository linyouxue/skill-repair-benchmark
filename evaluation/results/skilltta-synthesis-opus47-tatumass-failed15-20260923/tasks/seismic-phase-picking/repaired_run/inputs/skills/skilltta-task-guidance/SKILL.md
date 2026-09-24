---
name: skilltta-task-guidance
description: Task-specific operational guidance synthesized at test time from retrieved training examples.
---

# SKILL.md

## When to use
Use this skill when the target task requires **seismic phase picking** — identifying P-wave and S-wave arrival sample indices in multi-channel waveform traces stored as `.npz` files — and writing per-pick rows to a CSV. The binding contract requires:
- Reading every trace file in the provided input directory.
- Producing a CSV with exactly the columns `file_name`, `phase` ("P" or "S"), and `pick_idx` (integer sample index).
- Allowing zero, one, or multiple picks of each phase per file.
- Being graded by F1 with a tolerance defined in seconds (convert to samples using each file's `dt`).
- Meeting minimum F1 thresholds for P and S separately.

Before acting, gather:
- One sample file's keys, `data.shape`, `channels` order, `dt`, and dtype.
- The sampling rate (`1/dt`) and derived tolerance in samples (`round(tolerance_seconds / dt)`).
- Whether channel order is consistent (commonly E, N, Z with Z being vertical, best for P).
- Presence of GPU / installed packages (`seisbench`, `torch`, `obspy`, `scipy`).

## Possible Failure Modes
- **Rolling your own STA/LTA picker**: classical detectors typically miss the F1 thresholds needed here. Prefer a pretrained deep learning picker (e.g., SeisBench models like PhaseNet, EQTransformer) if available.
- **Wrong channel order / orientation**: passing channels in the wrong order to a model expecting ZNE vs ENZ severely degrades picks. Always reorder using the file's `channels` field to match the model's expected component order.
- **Ignoring per-file `dt`**: assuming a fixed sampling rate (e.g., 100 Hz) when files vary breaks the tolerance conversion and any model resampling requirement. Resample to the model's native rate (often 100 Hz) if needed, then map picks back to original indices.
- **Not preprocessing**: forgetting to detrend, demean, or bandpass filter (typically ~1–45 Hz) hurts SNR and picking quality.
- **Outputting probabilities instead of discrete picks**: the CSV needs integer sample indices from peak detection on the model's P/S probability curves, with a sensible threshold (e.g., 0.3 for P, 0.3 for S) and minimum inter-peak distance.
- **Emitting one row per file with both P and S columns**: the schema is one row per pick; a file with 1 P and 2 S picks yields 3 rows. Files with no picks contribute zero rows (this is allowed).
- **Index off-by-one after resampling**: when the model runs at a different sample rate, scale peak indices back: `orig_idx = round(peak_idx * dt_model / dt_file)`.
- **Missing files or crashes on one bad trace** aborting the whole run: wrap per-file processing in try/except and continue.
- **Writing floats or numpy types** to `pick_idx`: cast to plain Python `int`.
- **Copying constants from unrelated retrieved examples** (FFT, z-score, employee CSV code): these are unrelated tasks; do not treat their code as template.

## Possible procedures
1. **Inspect data**: load one `.npz`, print keys, `data.shape` (expect `(12000, 3)` or transpose), `channels`, `dt`. Decide whether to transpose to `(3, N)` since most models want channels-first.
2. **Choose a picker**:
   - Preferred: `seisbench.models.PhaseNet.from_pretrained("stead"|"instance"|"original")` or `EQTransformer`. These are trained specifically for P/S picking and easily clear the required F1.
   - Fallback: build an ObsPy `Stream` with proper `stats` (sampling_rate, channel codes) and call `model.classify(stream)` or `model.annotate(stream)`.
3. **Preprocess**:
   - Detrend, demean each channel.
   - Bandpass filter roughly 1–45 Hz (respect Nyquist).
   - Normalize per-trace (mean 0, std 1 or max-abs).
   - Resample to the model's expected rate if different from `1/dt`.
4. **Run inference** to get per-sample P and S probability curves aligned to the input length.
5. **Peak-pick** with `scipy.signal.find_peaks` using a probability threshold (start ~0.3) and `distance` corresponding to a physically reasonable refractory period (e.g., 1 s). Consider separate thresholds per phase; tune to trade precision vs recall for F1.
6. **Map indices back** to the original file's sample grid if resampling was used.
7. **Emit rows** `(file_name, phase, int(pick_idx))` and write CSV with a header. Sort or leave as-is — order is not evaluated, only rows.
8. **Recovery**: if a model isn't installed, `pip install seisbench` (which pulls torch/obspy). If offline, fall back to a tuned characteristic-function picker (kurtosis, AIC, or STA/LTA on Z for P and horizontals for S), but expect lower F1 — tune thresholds on a few files where you can sanity-check picks visually.

## Verification Checklist
- [ ] Confirmed `data.shape`, `channels` ordering, and `dt` on at least one file; reordered channels to match the model's expected components.
- [ ] Tolerance in samples computed per-file from `dt` (`round(0.1 / dt)`), not hardcoded.
- [ ] Preprocessing (detrend, filter, normalize, optional resample) applied consistently.
- [ ] Picker outputs discrete integer indices; probability threshold and minimum peak distance chosen to balance precision/recall for F1.
- [ ] CSV at the required output path has exactly the columns `file_name`, `phase`, `pick_idx` with header; `phase` values are only `"P"` or `"S"`; `pick_idx` is a Python `int` within `[0, n_samples-1]`.
- [ ] Files with zero picks contribute zero rows; files with multiple picks contribute multiple rows (schema allows this).
- [ ] All input files iterated; per-file exceptions caught so one failure doesn't drop the rest.
- [ ] Spot-checked a few picks: P pick precedes S pick, both within the trace length, and roughly aligned with an amplitude/energy rise on the appropriate components (Z for P, horizontals for S).
- [ ] Did not copy code or constants from unrelated retrieved examples (FFT, z-score, employee CSV).
- [ ] Did not overwrite or delete unrelated files under `/root/`.
