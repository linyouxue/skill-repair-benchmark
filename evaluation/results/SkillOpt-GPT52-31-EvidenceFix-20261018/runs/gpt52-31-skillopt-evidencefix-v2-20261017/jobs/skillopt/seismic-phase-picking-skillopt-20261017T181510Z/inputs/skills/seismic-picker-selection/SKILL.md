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



For benchmark tasks evaluated with strict timing tolerances, overall F1 is usually dominated by post-processing quality rather than raw detector sensitivity alone. Threshold calibration, duplicate suppression, abstention logic, and local refinement often improve scores more than swapping between modern pretrained pickers.
## STA/LTA (Short-Term Average / Long-Term Average)

### Advantages
- Runs very fast: Automatically operates in real-time
- Easy to understand & implement: Can optimize for different window lengths and ratios
- No prior knowledge needed: Does not require information about earthquake sources or waveforms
- Amplitude-based detector: Reliably detects large earthquake signals


- Useful as a secondary refinement stage around machine-learning candidate picks, where local onset timing can be improved without scanning the entire trace
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


- Probability outputs from models such as PhaseNet and EQTransformer can be post-processed and calibrated for benchmark-style precision/recall optimization rather than treated as fixed picks
### Limitations
- Out-of-distribution data issues: For datasets not represented in training data, expect larger automated pick errors (0.1-0.5 s) and missed picks
- Cannot pick phases completely buried in noise - Not quite as sensitive as template-matching
- Sometimes misses picks from larger earthquakes that are obvious to humans, for unexplained
reason



### Practical Guidance for High-Accuracy Automatic Picking

For offline benchmark evaluation where the score is tolerance-based F1 (for example ±0.1 s at 100 Hz = ±10 samples), the main challenge is balancing recall against duplicate or inaccurate picks. Pretrained deep pickers such as PhaseNet and EQTransformer usually outperform pure STA/LTA, but only when preprocessing and post-processing are carefully calibrated.

#### Recommended Workflow
1. Preprocess waveforms consistently with model expectations:
   - Remove mean and trend
   - Normalize amplitudes per trace or sliding window
   - Use the correct sampling rate (commonly 100 Hz)
   - Preserve 3-component orientation if available (Z/N/E)
2. Run a pretrained picker (PhaseNet or EQTransformer) to obtain continuous P and S probability curves rather than directly trusting emitted picks.
3. Apply post-processing to probability traces:
   - Smooth short spikes
   - Use per-phase thresholds
   - Suppress duplicate peaks within a refractory window
   - Enforce physically plausible P-to-S ordering
4. Optionally refine the final pick locally using STA/LTA onset refinement or AIC around the ML peak.

#### Thresholding and Abstention
Aggressive thresholds increase recall but can sharply reduce precision because multiple nearby picks count as false positives under strict F1 evaluation.

Typical starting points for 100 Hz local-event data:
- P threshold: 0.25-0.45
- S threshold: 0.20-0.40
- Minimum peak spacing: 0.3-1.0 s
- Peak width smoothing: 3-10 samples

If the maximum probability is weak or broad, abstaining can improve F1 more than emitting a low-confidence pick. A practical rule is:
- emit no pick if peak probability < threshold
- emit only the strongest surviving peak per phase unless multi-event traces are expected

#### Multiple Candidate Picks
Many models emit several local maxima. For benchmark-style scoring, uncontrolled multi-pick output often hurts precision.

Recommended decision rules:
- Keep only the top-1 or top-2 peaks per phase after non-maximum suppression
- Prefer the earliest strong P peak
- Require S picks to occur after the chosen P pick
- Reject S candidates with implausibly small P-S separation

For local earthquakes at 100 Hz, a useful heuristic window is:
- minimum S delay after P: 0.5-1.0 s
- maximum S delay after P: 20-30 s

#### Hybrid Refinement Strategies
Deep-learning probabilities are often accurate to within a few tenths of a second, but benchmark tolerances may be stricter. Small local refinements can materially improve F1:
- Run STA/LTA or kurtosis/AIC refinement in a narrow window around the ML peak (for example ±0.5-1.0 s)
- Snap the final pick to the first impulsive onset near the probability maximum
- Use classical characteristic functions only locally rather than across the whole trace

#### Ensemble and Consensus Approaches
When compute permits, combining models can improve robustness:
- Average or multiply normalized probability traces from PhaseNet and EQTransformer
- Accept picks only when two methods agree within ~0.1-0.3 s
- Use ML picks as proposals and reject candidates unsupported by simple signal-quality checks

#### Compact Checklist for 100 Hz Data
- Detrend and normalize all channels
- Verify sampling rate assumptions before inference
- Use probability traces instead of raw emitted picks
- Tune P and S thresholds independently
- Apply non-maximum suppression
- Enforce P before S ordering
- Use abstention for low-confidence traces
- Optionally refine with local STA/LTA or AIC
- Validate thresholds on a held-out subset before large-scale inference
## References
- This skill is a derivative of Beauce, Eric and Tepp, Gabrielle and Yoon, Clara and Yu, Ellen and Zhu, Weiqiang. _Building a High Resolution Earthquake Catalog from Raw Waveforms: A Step-by-Step Guide_ Seismological Society of America (SSA) Annual Meeting, 2025. https://ai4eps.github.io/Earthquake_Catalog_Workshop/
- Allen (1978) - STA/LTA method
- Perol et al. (2018) - Deep learning for seismic detection
- Huang & Beroza (2015) - Template matching methods
- Yoon and Shelly (2024), TSR - Deep learning vs template matching comparison
