---
name: output-validation
description: Run (not just plan) a local self-check of the generated JSON and NPZ
  outputs for format, consistency, and CSR integrity.
---

## Steps
1. After writing `/root/pred_instructions.json` and `/root/pred_dyn_masks.npz`, **execute** a validation script (e.g., a small Python snippet) and observe it completes with no assertions/errors.
2. Load both outputs:
   - `j = json.load(open("/root/pred_instructions.json"))`
   - `npz = np.load("/root/pred_dyn_masks.npz")`
3. Validate JSON structure:
   - Each key matches `"{start}->{end}"` with integer `start,end`.
   - Each value is a non-empty list of strings.
   - Each label is in `{Stay, Dolly In, Dolly Out, Pan Left, Pan Right, Tilt Up, Tilt Down, Roll Left, Roll Right}`.
4. Validate **sample-index coverage** (half-open):
   - Determine sampled frame count `S` from the NPZ keys (count consecutive `f_{i}_data` starting at `i=0`).
   - Ensure JSON intervals exactly cover `[0, S)` with no gaps/overlaps, and `0 <= start < end <= S` for each interval.
5. Validate NPZ structure:
   - `shape` exists and is `[H,W]` (int-like).
   - For every `i in [0, S)`, the keys `f_{i}_data`, `f_{i}_indices`, `f_{i}_indptr` all exist.
6. Validate CSR integrity for at least one frame (and ideally all):
   - `len(indptr) == H + 1`
   - `indptr[-1] == indices.size == data.size`
   - `indices` are within `[0, W)` (or empty)
7. Reporting rule: only claim “validated” in the final response if you actually ran the validation and observed success; otherwise state validation was not run.
## Expected Result
You have an observed (executed) validation run confirming the JSON interval mapping is well-formed and covers `[0,S)`, and the NPZ contains consistent per-frame CSR masks with the declared `shape`.
