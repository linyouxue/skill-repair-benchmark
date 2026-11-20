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

## Practical Workflow: Phase Picking with Deep-Learning Pickers

If the task is to produce P/S pick indices (or times) per trace, graded by a tolerance-based F1 (pick counted correct if within some small ±Δt of the human label), the following workflow usually works well. Keep the F1 trade-off in mind: *every* extra pick that is not within tolerance is a false positive.

1. **Inspect the data first.** Print per-channel `std`, sampling rate, amplitude scale, and the `channels` string for a few files. In particular, verify that the array you load is not zero-padded in unused component slots (see the pitfall in `obspy-data-api`). Running an ML picker on an all-zero trace returns a nearly-flat characteristic function and is a common cause of "the model doesn't detect anything".

2. **Preprocess the stream** before feeding it to the model. For local/regional events a safe default is `detrend("demean").detrend("linear").taper(0.05)` followed by a broadband bandpass (e.g. 2 Hz to `min(20, 0.45*fs)`). Confirm on a sample trace that the characteristic-function peak grows with filtering.

3. **Start with a deep-learning picker** via SeisBench (`PhaseNet`, `EQTransformer`, `PickBlue`, …). Pretrained weights trained on a dataset similar to the target region (e.g. `scedc` for California, `stead` for global) give a reasonable zero-shot baseline.

4. **Choose thresholds from the characteristic-function distribution**, not blindly. If the peak probabilities on representative traces sit near the default, lower the threshold (e.g. 0.05–0.1) and tighten precision with the post-processing below.

5. **Ensemble complementary pretrained models.** Running two or three models on the same stream and merging their picks lifts recall. Then collapse near-duplicates:
   - cluster picks per phase by proximity within the evaluation tolerance;
   - keep one pick per cluster, e.g. the highest-probability one or the model-majority winner;
   - optionally require more than one model to vote for low-probability picks, while keeping high-probability single-model picks.

6. **Apply physics-based sanity filters** when the task guarantees a single earthquake per trace:
   - at the same station, the P arrival must precede the S arrival;
   - the S–P separation for local-to-regional events is on the order of tenths of a second to a few seconds — implausibly large or negative gaps indicate a false pick;
   - picks far outside the sensible event window on a pre-cut trace are suspect.
   Use these as soft filters based on properties of your dataset; do **not** hard-code pick positions.

7. **Report in the required output format.** When the task asks for a sample index, convert each SeisBench `Pick.peak_time` to an integer sample via `int(round((peak_time - stream_starttime) / dt))` and drop picks that fall outside `[0, n_samples)`.

8. **Sanity-check the output distribution** before accepting it:
   - count picks per `(file, phase)` — many files with 3+ picks per phase usually indicates the merge step is too permissive;
   - count files without any pick — if this is a large fraction, revisit preprocessing and data loading rather than just lowering the threshold;
   - look at the P–S gap statistics — physically implausible outliers often reveal residual bugs.

If deep-learning picking alone cannot reach the required F1, STA/LTA or template matching may be added as a secondary detector for the subset of traces the ML picker misses, but spend the first debugging budget on data loading, preprocessing and ensemble/post-filtering.

## References
- This skill is a derivative of Beauce, Eric and Tepp, Gabrielle and Yoon, Clara and Yu, Ellen and Zhu, Weiqiang. _Building a High Resolution Earthquake Catalog from Raw Waveforms: A Step-by-Step Guide_ Seismological Society of America (SSA) Annual Meeting, 2025. https://ai4eps.github.io/Earthquake_Catalog_Workshop/
- Allen (1978) - STA/LTA method
- Perol et al. (2018) - Deep learning for seismic detection
- Huang & Beroza (2015) - Template matching methods
- Yoon and Shelly (2024), TSR - Deep learning vs template matching comparison
