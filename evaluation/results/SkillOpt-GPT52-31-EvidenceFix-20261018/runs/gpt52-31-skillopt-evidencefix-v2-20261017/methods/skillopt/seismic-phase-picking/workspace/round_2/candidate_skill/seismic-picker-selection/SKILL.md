---
name: seismic-picker-selection
description: This is a summary the advantages and disadvantages of earthquake event detection and phase picking methods, shared by leading seismology researchers at the 2025 Earthquake Catalog Workshop. Use it when you have a seismic phase picking task at hand.
---


# Seismic Event Detection & Phase Picking Method Selection Guide



## Benchmark Playbook (maximize F1 for automatic P/S picks)

This section is for **benchmark-style phase picking** where you are scored by **F1** with a strict time tolerance (e.g., ±0.1 s). In this setting, performance is often dominated by **post-processing** (thresholds, peak selection, duplicate suppression, constraints) more than by swapping between modern pretrained pickers.

### Recommended default stack (no training)
- Use **SeisBench pretrained deep pickers**.
- Prefer working from **probability traces** (via `annotate`) and doing your own peak extraction, rather than relying on a model’s built-in `classify` defaults.

### Which pretrained model to try first (SeisBench)
- **PhaseNet**: strong default for local events; fast; often best when there is a single clear event in each window.
- **EQTransformer**: can be more robust for emergent onsets / noisy windows / multiple arrivals, but slower and can emit more candidate picks (can hurt precision unless you suppress duplicates).

Practical rule:
- If you see many spurious picks or unstable S picks with PhaseNet, try EQTransformer + stricter duplicate suppression.
- If you need speed and windows usually contain one event, start with PhaseNet.

### Preprocessing that usually helps F1 (100 Hz local-event windows)
- Detrend/demean each channel.
- Light bandpass often helps (typical: **1–20 Hz**, 2–4 corners, zero-phase) if noise is strong.
- Per-trace standardization: `(x - mean) / (std + 1e-6)` (keeps models stable across amplitude scales).
- Ensure sampling rate is correct; **±0.1 s at 100 Hz = ±10 samples** tolerance.

### Turn probabilities into picks (operational recipe)
1. Get per-sample probabilities `pP[t]`, `pS[t]` from the model.
2. Optionally smooth (moving average **3–7 samples**) to remove single-sample spikes.
3. Find **local maxima** above a threshold.
4. Apply **non-maximum suppression** (NMS): keep only the highest peak within a refractory window.
5. Apply physical constraints (below), then output picks.

### Threshold calibration (precision/recall tuning)
You should tune P and S separately.
- Start ranges for 100 Hz local-event data:
  - `thr_P`: **0.25–0.55**
  - `thr_S`: **0.20–0.50** (S is often weaker/messier)
  - NMS minimum spacing: **0.3–1.0 s** (30–100 samples)
  - Minimum peak prominence (if used): **0.05–0.20**

Heuristic tuning loop (no labels available):
- If you output exactly one pick per phase and MAE is huge, you are likely taking the wrong global maximum; switch to local peaks + constraints.
- If recall is low (many missing picks), lower thresholds or reduce prominence.
- If precision is low (too many picks), increase thresholds and/or increase NMS window.

### Duplicate suppression and “top-k” candidate policy
Benchmark F1 usually penalizes extra picks strongly.
- Default: **top-1 pick per phase per file** after NMS.
- Consider **top-2** only if you expect multiple events per window and your evaluator can match one-to-one without harsh FP penalties. If unsure, top-1 is safer.

### Abstention (when emitting no pick helps)
If the trace is low confidence, abstaining can improve F1.
- If `max(pP) < thr_P`, output **no P**.
- If `max(pS) < thr_S`, output **no S**.

### Simple physical constraints that often boost F1
Apply after peak finding:
- **P before S**: only allow S candidates with `tS > tP`.
- Plausible **P–S separation window** (100 Hz local events):
  - `tS - tP >= 0.5 s` (>= 50 samples)
  - `tS - tP <= 25 s` (<= 2500 samples)

If no S peak satisfies constraints, either emit only P or relax `thr_S` slightly (but avoid flooding with S picks).
## Overview: Method Tradeoffs

When choosing an event detection and phase picking method, consider these key tradeoffs:

| Method | Generalizability | Sensitivity | Speed, Ease-of-Use | False Positives |
|--------|------------------|-------------|-------------------|-----------------|
| STA/LTA | High | Low | Fast, Easy | Many |
| Manual | High | High | Slow, Difficult | Few |
| Deep Learning | High | High | Fast, Easy | Medium |
| Template Matching | Low | High | Slow, Difficult | Few |

- **Generalizability**: Ability to find arbitrary earthquake signals
- **Sensitivity**: Ability to find small earthquakes


**Key insight:** Each method has strengths and weaknesses. Purpose and resources should guide your choice.

## STA/LTA (Short-Term Average / Long-Term Average)



### How STA/LTA helps in an ML-first benchmark pipeline
Use STA/LTA (or AIC/kurtosis) as a **local refinement** tool, not as the primary picker:
- Take the ML pick as a proposal.
- Search a small window around it (e.g., ±0.5–1.0 s) for the sharpest onset.
- This can reduce timing error enough to cross a ±0.1 s tolerance without adding false positives.
### Advantages
- Runs very fast: Automatically operates in real-time
- Easy to understand & implement: Can optimize for different window lengths and ratios
- No prior knowledge needed: Does not require information about earthquake sources or waveforms
- Amplitude-based detector: Reliably detects large earthquake signals

### Limitations
- High rate of false detections during active sequences
- Automatic picks not as precise
- Requires manual review and refinement of picks for a quality catalog

---

## Template Matching

### Advantages
- Optimally sensitive detector (more sensitive than deep-learning): Can find smallest earthquakes buried in noise, if similar enough to template waveform
- Excellent for improving temporal resolution of earthquake sequences
- False detections are not as concerning when using high detection threshold

### Limitations
- Requires prior knowledge about earthquake sources: Need **template waveforms** with good picks from a preexisting catalog
- Does not improve spatial resolution: Unknown earthquake sources that are not similar enough to templates cannot be found
- Setup effort required: Must extract template waveforms and configure processing
- Computationally intensive

---

## Deep Learning Pickers



### Practical SeisBench notes (PhaseNet / EQTransformer)

**Prefer `annotate` for control.** Use `model.annotate(stream)` to get probability traces and then implement your own peak picking + constraints. Built-in `classify` is convenient, but its default thresholds and multi-pick behavior may not be optimal for strict F1.

**Post-processing checklist (per file):**
- Extract `P` and `S` probability arrays.
- Run peak finding with `(height=thr, distance=nms_samples)`.
- Keep **one** best P.
- For S, keep the best peak in `[P + min_ps, P + max_ps]`.
- If the best candidate is below threshold, abstain.
### When to Use
- Adds most value when existing seismic networks are sparse or nonexistent
- Automatically and rapidly create more complete catalog during active sequences
- Requires continuous seismic data
- Best on broadband stations, but also produces usable picks on accelerometers, nodals, and Raspberry Shakes
- **Use case**: Temporary deployment of broadband or nodal stations where you want an automatically generated local earthquake catalog

### Advantages
- No prior knowledge needed about earthquake sources or waveforms
- Finds lots of small local earthquakes (lower magnitude of completeness, Mc) with fewer false detections than STA/LTA
- Relatively easy to set up and run: Reasonable runtime with parallel processing. SeisBench provides easy-to-use model APIs and pretrained models.

### Limitations
- Out-of-distribution data issues: For datasets not represented in training data, expect larger automated pick errors (0.1-0.5 s) and missed picks
- Cannot pick phases completely buried in noise - Not quite as sensitive as template-matching
- Sometimes misses picks from larger earthquakes that are obvious to humans, for unexplained
reason



### Common failure modes (and fixes)
- **Global-maximum picking** across the whole window often lands on noise bursts or late coda → use local peaks + thresholds + constraints.
- **Too many picks** (precision collapse) → increase `thr`, increase NMS spacing, reduce to top-1.
- **Too few picks** (recall collapse) → lower `thr`, lower prominence, allow smaller NMS spacing, or prefer PhaseNet for speed and smoother outputs.
- **Bad S picks** → enforce P-before-S and a P–S window; tune `thr_S` separately (often lower than `thr_P`).
- **Large systematic offsets** → verify sample rate (`dt`), channel ordering, and that the trace start time used for index conversion is consistent.
## References
- This skill is a derivative of Beauce, Eric and Tepp, Gabrielle and Yoon, Clara and Yu, Ellen and Zhu, Weiqiang. _Building a High Resolution Earthquake Catalog from Raw Waveforms: A Step-by-Step Guide_ Seismological Society of America (SSA) Annual Meeting, 2025. https://ai4eps.github.io/Earthquake_Catalog_Workshop/
- Allen (1978) - STA/LTA method
- Perol et al. (2018) - Deep learning for seismic detection
- Huang & Beroza (2015) - Template matching methods
- Yoon and Shelly (2024), TSR - Deep learning vs template matching comparison
