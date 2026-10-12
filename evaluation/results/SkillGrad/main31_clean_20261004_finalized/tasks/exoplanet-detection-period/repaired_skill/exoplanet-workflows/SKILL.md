---
name: exoplanet-workflows
description: Workflows and validation checks for exoplanet detection from light curves.
---

# Exoplanet Detection Workflows

## Pipeline skeleton

1. Load light curve and confirm units/time system.
2. Quality filtering (flags) and basic visualization.
3. Preprocess (outliers → detrend/flatten).
4. Period search (TLS/BLS for transits; Lomb–Scargle for general variability).
5. Validate candidate(s) with transit-specific checks.
6. Refine period locally and report final period with uncertainty.

## Validation: handle harmonics explicitly (P vs 2P vs P/2)

Transit searches often return harmonically related candidates (P, 2P, sometimes P/2). Raw periodogram strength (TLS SDE, BLS power) can favor an alias.

Checklist:
- Always inspect a small candidate set `{P, 2P, (P/2)}` when harmonics appear.
- Prefer **odd/even depth consistency** and **phase-fold coverage** over raw power/SDE for transit signals.
- If P shows alternating depths (odd/even mismatch) and 2P removes that mismatch, treat P as a half-period alias and choose 2P.

Read references/period-alias-disambiguation.md when your top candidates are near harmonics and selection is ambiguous.
Skip when there is a single isolated candidate and the folded transit is unambiguous.

## Common pitfalls

- Selecting the highest-power/SDE peak even after diagnostics indicate it is a half-period alias.
- Treating harmonic peaks as independent “planets” before resolving the fundamental period.
