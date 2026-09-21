---
name: seismic-picker-selection
description: This is a summary the advantages and disadvantages of earthquake event detection and phase picking methods, shared by leading seismology researchers at the 2025 Earthquake Catalog Workshop. Use it when you have a seismic phase picking task at hand.
---


# Seismic Event Detection & Phase Picking Method Selection Guide

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

## References
- This skill is a derivative of Beauce, Eric and Tepp, Gabrielle and Yoon, Clara and Yu, Ellen and Zhu, Weiqiang. _Building a High Resolution Earthquake Catalog from Raw Waveforms: A Step-by-Step Guide_ Seismological Society of America (SSA) Annual Meeting, 2025. https://ai4eps.github.io/Earthquake_Catalog_Workshop/
- Allen (1978) - STA/LTA method
- Perol et al. (2018) - Deep learning for seismic detection
- Huang & Beroza (2015) - Template matching methods
- Yoon and Shelly (2024), TSR - Deep learning vs template matching comparison



## Executable Workflow for Local Three-Component NPZ Traces

Process each file independently and preserve its original sample grid. Load `data`, `dt`, and `channels`; require finite two-dimensional data, positive finite `dt`, and a channel count matching one data dimension. Orient the array as samples by channels only when this is unambiguous, parse and normalize the comma-separated channel labels, and reject or log malformed files. Map components from labels (typically a suffix such as `Z` identifies vertical and `N/E`, `1/2` identify horizontals); never assume that the vertical channel is column 0. Keep the original array, channel map, sample count, and `dt` available for final index conversion.

Estimate noise per component from a quiet early or low-energy portion using a robust scale such as MAD, while guarding against records with no quiet portion, clipping, NaNs, or nearly zero variance. Work on copies: remove mean/trend and optionally apply a conservative zero-phase bandpass whose corners are valid for that file's Nyquist frequency. Do not resample or trim without retaining the offset. Prefer a verified pretrained picker first when it is installed and its channel order, sampling rate, and output time origin can be mapped reliably to this trace; treat its P/S outputs as candidates rather than unquestionable truth. If unavailable, incompatible, or low-confidence, use a deterministic fallback based on robustly normalized multiscale STA/LTA or envelope/energy-ratio rises.

Generate P and S candidates separately. For P, prioritize an impulsive onset on the identified vertical component, supported by the three-component norm and cross-channel timing agreement. For S, prioritize a later increase in horizontal energy (the norm of the two identified horizontals), supported by horizontal envelopes, energy ratios, and the full three-component signal. Search the full record for S so an absent P does not suppress a valid S; a P candidate may only narrow or prioritize a later S search. Use phase-specific adaptive thresholds based on the noise estimate rather than one universal amplitude threshold. For each trigger, refine to the earliest consistent local onset by searching nearby samples in the original-rate feature or filtered waveform and retain the original sample index.



## Candidate Selection, Tolerance, and Output

Score P and S candidates separately using detector strength, onset sharpness, SNR over the local noise estimate, supporting-component agreement, and (for S) delayed horizontal-energy evidence. Abstain when evidence is weak or confined to an incomplete edge window. Apply phase-specific non-maximum suppression: merge nearby candidates within a refractory interval and keep the strongest, best-supported, or best-refined candidate, while retaining multiple arrivals only when they are separated and independently supported. Use the grading resolution `tol_samples = max(1, round(0.1 / dt))` when tuning refinement and duplicate/merge distances; do not move a pick by this tolerance or fabricate a pick. Apply P-before-S only as a cautious preference when both picks are credible and their separation is physically plausible; do not discard a credible phase solely because the other phase is absent or ordered unexpectedly.

Run a small deterministic validation loop on representative quiet, noisy, clipped, and multi-arrival traces. Compare several conservative threshold/window settings and inspect agreement among the pretrained picker (if usable), STA/LTA, envelope, and energy-ratio detectors. Favor settings that improve separate P and S precision/recall at the per-file timing tolerance, not settings that merely produce more rows. Then process all files with the selected settings and deduplicate deterministically.

Write `/root/results.csv` with exactly `file_name,phase,pick_idx`. Emit only `P` or `S`, use the exact input filename, and convert every retained candidate to an integer index in `[0, n_samples)`, accounting for any processing offset and retaining the original sample coordinate. Validate the CSV after writing: required headers must exist, indices must be integers rather than NaN or float strings, filenames must correspond to processed files, and duplicate `(file_name, phase, pick_idx)` rows must be removed. A file may have no P or no S, and an entirely empty result is valid if the header remains present.
