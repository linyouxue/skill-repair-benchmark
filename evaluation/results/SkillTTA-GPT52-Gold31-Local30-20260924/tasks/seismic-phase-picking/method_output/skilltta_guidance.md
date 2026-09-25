# SKILL.md

## When to use
Use this skill when you must **perform seismic phase picking** on a collection of waveform trace files (e.g., `.npz`) where each file contains:
- multichannel waveform samples (fixed-length array, samples × channels),
- a sampling interval `dt` (seconds),
- channel names (to interpret vertical vs horizontal components),

and you must output a **single CSV** listing detected **P** and **S** arrival **sample indices** per file. The scorer evaluates picks with a **time tolerance** (e.g., 0.1 s) converted to **index tolerance** via `dt`, and performance is measured by **F1** (so precision/recall tradeoffs matter).

Before acting, gather evidence from the data format and contents:
- Confirm keys present in each file (`data`, `dt`, `channels`) and the array shape/orientation.
- Determine sampling rate consistency (is `dt` constant across files?).
- Identify which channel is vertical (often best for P) and which are horizontal (often best for S), using the provided channel names.
- Inspect a few traces to understand noise level, baseline drift, and whether arrivals are impulsive or emergent.

## Possible Failure Modes
- **Wrong output schema**: CSV missing required columns (`file_name`, `phase`, `pick_idx`), wrong column names/case, extra columns, or wrong quoting for phase labels.
- **Wrong index convention**: outputting time in seconds instead of sample index, using 1-based indexing instead of 0-based, or floating indices.
- **Not converting tolerance correctly**: ignoring `dt` variability across files when translating 0.1 s to sample tolerance.
- **Channel misuse**: picking P/S on an arbitrary component without considering vertical vs horizontals; mixing channel order vs channel names.
- **Overpicking (precision collapse)**: emitting many candidate picks per trace without suppression/ranking, harming F1.
- **Underpicking (recall collapse)**: too strict thresholds leading to many files with no picks.
- **Instrument/noise artifacts**: triggering on spikes, clipping, long-period drift, or onset-like noise bursts instead of true arrivals.
- **Preprocessing distortions**: applying filters that smear onset timing (phase delay) or using non–zero-phase filtering that shifts arrivals.
- **Edge/shape errors**: mishandling (samples × channels) vs (channels × samples), NaNs, constant traces, or unexpected dtype.
- **File naming issues**: writing full paths instead of base file names, or mismatching names relative to what the evaluator expects.
- **Non-determinism**: randomness (if used) causing unstable picks across runs.

## Possible procedures
1. **Load and normalize per trace**
   - Enumerate files in the target directory; load each `.npz`.
   - Parse `channels` into a list and align it with the second dimension of `data`.
   - Basic QC: check for NaNs/infs, constant segments, extreme outliers; decide whether to skip or robustly handle.
   - Demean/detrend each channel; optionally standardize by robust scale (MAD) to make thresholds more transferable.

2. **Component selection strategy (decision point)**
   - **P picking**: prefer the most “vertical-like” channel (often ends with `Z`), or fall back to the channel with the strongest early impulsive energy.
   - **S picking**: prefer horizontals (often `N/E` or `1/2`) and/or use a combined horizontal magnitude.
   - If channel naming is ambiguous, use a data-driven heuristic (e.g., choose component(s) with highest post-onset energy contrast).

3. **Preprocess to enhance onsets**
   - Apply bandpass filtering suited for local/regional arrivals (choose conservative bands to avoid removing onset energy).
   - Prefer **zero-phase filtering** (forward–backward) to reduce timing bias.
   - Optionally compute an envelope, short-term energy, or squared amplitude to stabilize triggering.

4. **Compute a characteristic function for triggers**
   - Use one or more onset detectors (choose based on observed data):
     - **STA/LTA ratio** (classic, robust baseline).
     - **AIC picker** (good for impulsive P onsets).
     - **Kurtosis / higher-order statistics** (helps detect sharp changes).
     - **Polarization attributes** (P more linear/vertical; S more transverse) if channels support it.
   - Keep the detector output as a 1D curve per phase target (P-curve, S-curve).

5. **Candidate generation + suppression**
   - Find peaks/threshold crossings in the characteristic function.
   - Enforce **minimum separation** between picks (non-maximum suppression) to prevent clusters of near-duplicates.
   - Rank candidates by score (peak height, STA/LTA level, slope, energy jump).

6. **P then S logic (decision point)**
   - Often pick **P first**, then search for **S** in a plausible window after P (relative timing constraints can reduce false S picks).
   - If no reliable P, optionally allow S-only picks rather than forcing a bad P.

7. **Control precision/recall to optimize F1**
   - Start with conservative thresholds to avoid many false positives, then relax if too many missed traces.
   - Because multiple picks are allowed, prefer **a small number of high-confidence picks** per file (e.g., top-1 or top-k with strong suppression), rather than many weak candidates.
   - Tune per-phase thresholds separately (S is often harder; may need different windows/thresholds).

8. **Write results**
   - For each accepted candidate, write one row: `{file_name, phase, pick_idx}`.
   - Use the file’s base name (not full path).
   - Ensure `pick_idx` is an integer within `[0, n_samples-1]`.

9. **Recovery / iteration loop**
   - If results look poor on spot checks: adjust filtering band, STA/LTA windows, or selection rules for components and search windows.
   - If picking shifts are suspected: verify filter phase characteristics and any resampling operations.

## Verification Checklist
- [ ] All input files were attempted; failures (if any) are handled explicitly (skip with logging vs crash).
- [ ] For every pick: `pick_idx` is **integer**, **0-based**, and within the sample range of that trace.
- [ ] Output CSV exists at the required path and contains **exactly three columns** named: `file_name`, `phase`, `pick_idx`.
- [ ] `phase` values are exactly `"P"` or `"S"` (correct case; no extra whitespace).
- [ ] `file_name` entries match the actual trace file names (prefer base name; no directory prefixes unless required).
- [ ] `dt` is used to compute any time-based windows/tolerances; no hard-coded sample tolerance that ignores per-file `dt`.
- [ ] Picks per file are not excessively many (check for overpicking that will reduce precision/F1).
- [ ] Preprocessing does not introduce systematic time shifts (confirm zero-phase filtering or otherwise account for delay).
- [ ] No reliance on concrete details from retrieved examples (paths, IDs, constants, plotting conventions) that are unrelated to this task.
- [ ] If evidence is ambiguous (unclear channels/noise), rerun a small subset with alternative component heuristics and compare pick stability before finalizing.
