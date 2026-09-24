---
name: seismic-picker-selection
description: Choose an appropriate phase picking strategy (deep learning vs STA/LTA
  vs template matching) and tune it to balance recall/precision for catalog-quality
  picks.
---

## Steps
1. Prefer **deep learning pickers** (e.g., PhaseNet via SeisBench) when you need high sensitivity/generalizability across many traces without templates.
2. Use thresholding and peak-distance rules to control false positives; do not assume exactly one event or one P/S pair in a continuous window.
3. If deep learning outputs are unstable due to data scale, rescale/normalize waveforms before inference (especially when raw amplitudes are extremely small).
4. Consider simple signal-based checks (e.g., STA/LTA-style gating) only as a *supplement* for rejecting obvious noise segments, not as the primary picker if high timing precision is required.
## Expected Result
A method choice and tuning approach that targets high F1 by improving timing robustness and reducing forced false positives on low-SNR or phase-absent traces.
