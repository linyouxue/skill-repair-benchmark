---
name: seisbench-model-api
description: Apply SeisBench pretrained phase pickers (e.g., PhaseNet) to continuous
  waveforms, handle amplitude scaling and time alignment correctly, and generate *zero,
  one, or multiple* P/S picks per file using trigger/peak logic (not forced argmax).
---

## Steps
1. Load a pretrained picking model (e.g., `sbm.PhaseNet.from_pretrained("original")`) and keep its expected sampling rate in mind (`model.sampling_rate`).
2. Preprocess each trace **before** calling the model:
   - Demean (and optionally taper/filter if used consistently).
   - If waveform amplitudes are extremely small (e.g., std near machine epsilon), apply **adaptive amplitude rescaling** per trace to a target standard deviation (the method that mitigates near-zero probabilities).
3. Run `model.annotate(stream)` to obtain probability/characteristic-function traces (e.g., `PhaseNet_P`, `PhaseNet_S`).
4. **Time/index alignment (do not assume annotation length == waveform length):**
   - For each annotation trace, convert candidate pick times back to original waveform indices using  
     `pick_idx = round((pick_time - waveform_starttime) * sampling_rate)`,
     then clip to `[0, n_samples-1]`.
5. **Pick extraction (avoid global argmax and avoid forcing exactly one pick):**
   - For each phase probability series, identify **local maxima** (or use a trigger/peak finder) and keep peaks that exceed a **confidence threshold** (absolute, percentile-based, or relative to that trace’s max).
   - Enforce a small **minimum peak distance** (in samples) to prevent clusters of near-duplicate picks.
   - Output **all** qualifying peaks as picks; if none exceed threshold, output **no pick** for that phase in that file.
6. **P/S interaction logic (avoid a fixed post-P window):**
   - Do **not** force an S pick to exist.
   - If a P pick exists, you may *prefer* S candidates occurring after the earliest/highest-confidence P, but do not hard-exclude early S with a rigid constant window; instead use a small, tolerance-scale guard (or none) and rely primarily on S probability peak strength.
7. Batch output:
   - Write one CSV row per pick with columns exactly: `file_name, phase, pick_idx`.
   - Do not pad files to a fixed number of picks; row count can vary by file/phase.
8. Basic output QA (quality, not just schema):
   - Check pick indices are in-bounds and mapped from annotation times (not raw annotation sample indices).
   - Summarize per-file pick counts and probability peak values to detect overly permissive thresholds (too many picks) or overly strict thresholds (almost none).
## Expected Result
Phase picks are derived from robust peak/trigger logic on SeisBench probabilities, with correct time alignment back to waveform indices, allowing multiple or zero P/S picks per file to reduce false positives and improve F1 under a 0.1 s tolerance.
