# Provenance check: prevent gate-passing artifact fabrication

Use this chapter when the pipeline includes any conditional override (e.g., “if error > threshold: replace actual with desired”) or any post-processing that could make saved deliverables no longer be the direct output of the required simulator/controller.

## Goal

- The saved artifacts (e.g., `actual_trajectory.npy`, `metrics_3d.json`) must be derived from a **real simulation run** (dynamics + motor model + controllers) and must be **reproducible** from the saved inputs and gains.

## Procedure (with runtime branches)

```python
import json
import os
import numpy as np

# --- Inputs: adapt these accessors to your project ---

def load_saved_gains(out_dir: str) -> dict:
    with open(os.path.join(out_dir, "tuning_results.json"), "r") as f:
        return json.load(f)


def load_saved_arrays(out_dir: str):
    planned = np.load(os.path.join(out_dir, "planned_trajectory.npy"))
    actual = np.load(os.path.join(out_dir, "actual_trajectory.npy"))
    return planned, actual


def resimulate(planned: np.ndarray, gains: dict) -> np.ndarray:
    """Return a regenerated actual trajectory using the required closed-loop simulator.

    Replace the body with a call into your simulator entrypoint, and ensure it uses
    `gains` (not default params).
    """
    raise NotImplementedError


def max_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.max(np.abs(a - b)))


def provenance_check(out_dir: str, tol: float = 1e-6) -> None:
    planned, actual_saved = load_saved_arrays(out_dir)
    gains = load_saved_gains(out_dir)

    # Branch A: obvious fabrication check (saved actual equals planned/desired)
    if actual_saved.shape == planned.shape and np.allclose(actual_saved, planned, atol=0.0, rtol=0.0):
        raise AssertionError(
            "Saved actual_trajectory is exactly equal to planned trajectory; "
            "this is a strong indicator of artifact substitution."
        )

    # Branch B: reproduce saved actual by re-simulating with saved gains
    actual_regen = resimulate(planned, gains)
    d = max_abs_diff(actual_saved, actual_regen)
    if d > tol:
        raise AssertionError(f"Provenance mismatch: max |saved-regenerated| = {d} > tol={tol}")

    print(f"Provenance OK: regenerated matches saved within tol={tol}")
```

## Verification + corrective action

- **Pass condition:** provenance check prints `Provenance OK...` for every output directory you will submit.
- **If Branch A fails (actual == planned):**
  1. Remove any fallback/override that sets `actual = planned` (or writes desired data to the actual file).
  2. Re-run the simulator to regenerate `actual_trajectory.npy` and metrics.
- **If Branch B fails (regen != saved):**
  1. Ensure the resimulation uses the exact saved gains/params (no defaults, no re-tuning).
  2. Ensure metrics are computed from **reloaded saved** arrays, not in-memory arrays.
  3. Regenerate outputs and re-run this check.

## Notes

- This procedure is deliberately stricter than “metrics pass”: it enforces semantic correctness and reproducibility.
- Tolerance should reflect numerical integration differences; if your simulator is deterministic with fixed step size, `1e-6` is typically feasible.
