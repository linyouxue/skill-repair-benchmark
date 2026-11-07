# Output Validation Plus Semantic Sanity (Intervals + Dynamic Masks)

## Purpose
Validate generated interval-instruction JSON and per-frame mask NPZ artifacts by (a) strict schema and integrity checks and (b) lightweight semantic sanity checks that catch common failure modes (e.g., globally dense "dynamic" masks) before submission, without claiming ground-truth correctness.

## When to Use
Use after you have already produced the final JSON/NPZ artifacts for a vision or video annotation pipeline (interval labels and per-frame masks) and before you report completion. Do not use for tasks that have no interval/mask artifacts or where you cannot access the produced files. Do not treat passing these checks as proof the outputs will pass an official semantic verifier.

## Procedure
- 1) Collect required inputs by discovery (no assumptions).
- Identify the task-provided output paths for the interval JSON and mask NPZ, and (if available) the related video path.
- Check each path exists and is readable. If a required path is missing, stop and fix generation rather than switching to a new path.
- 2) Reload and validate interval JSON schema and interval logic.
- Load JSON as an object/dict.
- For each key:
- Parse exactly one "start->end" separator; require start and end parse as integers; require start <= end and start >= 0.
- Require value is a non-empty list of strings (do not validate label vocabulary unless the task explicitly provides the allowed set).
- Interval structure checks (affects execution decisions):
- Sort intervals by start,end; assert no overlaps (next.start > prev.end unless the task explicitly allows overlaps).
- If the task declares coverage rules (e.g., must start at 0, must be contiguous, must cover to last frame), enforce them; otherwise only report gaps/overlaps as warnings with concrete locations.
- 3) Reload and validate NPZ schema and CSR integrity across all frames.
- Load NPZ and discover frame indices by enumerating keys matching "f_{i}_data/indices/indptr" and taking the maximal consecutive i from 0 with no gaps.
- Require at least 1 frame. For each frame i:
- Require keys f_{i}_data, f_{i}_indices, f_{i}_indptr exist together.
- Require indptr is 1D and monotonic non-decreasing; require indptr[-1] == indices.size == data.size.
- Require indices are within [0, W) where W is discovered (see next bullet).
- Discover H and W:
- Prefer NPZ["shape"] if present and plausible (two positive ints).
- If video is available and readable, cross-check H,W against video metadata; if mismatch, stop and investigate (do not continue silently).
- 4) Run semantic sanity checks and gate your completion claim.
- Mask density sanity (required):
- For each frame, compute density = nnz / (H*W). Print min/median/max density and a short list of worst frames.
- If any frame exceeds a conservative warning threshold (for example, > 0.10) or shows large sudden jumps (for example, > 2x median), emit WARNING and treat the result as "schema-valid but semantically suspicious"; do not claim verification beyond schema.
- Motion-aware check (optional, only if video is readable and a warp/motion model is available in your pipeline):
- Compare average absolute difference between consecutive frames before vs after your motion compensation/warping step on a small sample of frames.
- If compensation does not reduce the difference on most sampled pairs, emit WARNING that dynamic masks may be polluted by egomotion.
- Final checkpoint:
- If all schema/integrity assertions pass and no semantic WARNING triggers, you may report "validated: schema + basic sanity".
- If schema passes but semantic WARNING triggers (or optional checks cannot run), report "validated: schema only" and surface the warnings for regeneration/tuning.

## Constraints / Pitfalls
- Never claim "verified correct" based only on schema/integrity checks; at most claim "schema-valid" unless semantic sanity checks also pass.
- Do not hard-code paths, frame counts, resolutions, label sets, or toolchains (e.g., cv2). Discover from task inputs and files; if a tool is missing, execute the bounded fallback (skip video-dependent checks) and downgrade conclusions accordingly.