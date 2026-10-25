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


## Recommended Default for F1-Scored Phase Picking Tasks

For benchmark/evaluation tasks that score P and S picks by F1 with a tight tolerance (e.g., ±0.1 s, which is ±10 samples at 100 Hz), **the default choice should be a SeisBench pretrained deep-learning picker** (PhaseNet or EQTransformer). STA/LTA is too imprecise; template matching requires templates you don't have; manual picking doesn't scale. See `seisbench-model-api/SKILL.md` for the concrete recipe.

### Critical warning: S-wave F1 is systematically lower than P-wave F1

At the same probability threshold, S-wave F1 is typically **5–10% lower** than P-wave F1 because S arrivals are emergent, lower-SNR, and often masked by the P coda. Many tasks set a stricter S threshold (e.g., P≥0.7, S≥0.6) in the grader, so the picker must not be tuned symmetrically. To maximize S-wave F1:

1. **Use asymmetric detection thresholds**: lower `S_threshold` relative to `P_threshold` (e.g., P=0.3, S=0.1–0.2 in SeisBench `classify`/`annotate`). Symmetric thresholds are the single most common cause of marginal S-wave failures.
2. **Ensure horizontal components (N, E) are present and correctly ordered**: SeisBench models expect channel order Z, N, E (or 3, 2, 1 for ordinals). If your trace has order like `DPE, DPN, DPZ`, reorder to `Z, N, E` before inference — S energy lives on the horizontals, and swapped/missing horizontals silently cripple S recall.
3. **Consider ensembling multiple pretrained weights** (e.g., average PhaseNet `stead`, `instance`, `scedc` outputs, or combine PhaseNet + EQTransformer) and keep per-phase picks that pass the per-phase threshold. This typically adds a few percent to S-wave F1.
4. **Verify sample-index conversion**: SeisBench may internally resample (e.g., to 100 Hz). When converting a returned `UTCDateTime` pick back to a sample index in the *original* trace, use the original `dt`/sampling rate and the original trace start time — not the resampled rate. Off-by-resampling-factor errors look like systematic offsets of tens to hundreds of samples and will destroy F1 at ±10-sample tolerance.

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
