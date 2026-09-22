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

### Practical tips to maximize F1 with pretrained DL pickers
When the evaluation tolerance is tight (e.g. ±0.1 s) and the target F1 threshold is high, the following are usually decisive:

1. **Preprocess the stream** before calling the model: `detrend("demean")`, `detrend("linear")`, a light cosine `taper`, and a bandpass filter appropriate for the target earthquakes (e.g. 1–45 Hz for local events at 100 Hz). Resample to `model.sampling_rate` if needed.
2. **Match the model to the data distribution.** For California / Geysers / NC-style local earthquakes, `PhaseNet` weights `scedc`, `stead`, or `instance` typically outperform `original`. For OBS data use `PickBlue`/`obs`. When unsure, run 2–3 candidates and compare.
3. **Tune P/S thresholds separately.** S waves are almost always the harder phase; if S recall is limiting F1, lower `S_threshold` (e.g. 0.1–0.2) while keeping `P_threshold` higher. Verify per-phase precision/recall, not just aggregate.
4. **Ensemble across models or weights.** Union of picks (with de-duplication within ±0.05 s) or intersection (picks confirmed by ≥2 models) trades recall vs precision — pick whichever the metric rewards. This often closes the last few percentage points of F1 for out-of-distribution data.
5. **Respect component availability.** S detection depends heavily on horizontal components. If a station only recorded Z (single-component), do not fabricate horizontals; accept that S recall on those traces will be lower and don't emit fake S picks.

## References
- This skill is a derivative of Beauce, Eric and Tepp, Gabrielle and Yoon, Clara and Yu, Ellen and Zhu, Weiqiang. _Building a High Resolution Earthquake Catalog from Raw Waveforms: A Step-by-Step Guide_ Seismological Society of America (SSA) Annual Meeting, 2025. https://ai4eps.github.io/Earthquake_Catalog_Workshop/
- Allen (1978) - STA/LTA method
- Perol et al. (2018) - Deep learning for seismic detection
- Huang & Beroza (2015) - Template matching methods
- Yoon and Shelly (2024), TSR - Deep learning vs template matching comparison
