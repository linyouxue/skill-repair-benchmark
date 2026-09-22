### deliverables-gate-always-write-artifacts | workflow | always emit required JSON+NPZ artifacts and verify on-disk existence before terminating
- anchor: output-validation
- appeared_in: iter_0, iter_1
- description: The executor sometimes completes (or prematurely stops) without writing any required output files. In this task family, the harness expects two artifacts at fixed absolute paths: `/root/pred_instructions.json` (interval keys mapping to allowed motion labels) and `/root/pred_dyn_masks.npz` (CSR-encoded dynamic object masks for each sampled frame plus `shape=[H,W]`). When either or both files are missing, evaluation yields an empty/invalid inventory regardless of analysis quality.

  Mechanism observed so far:
  - The run can terminate (“end_turn”) without invoking the pipeline skills at all, so no video is read, no sampling indices are produced, and no artifacts are created.
  - Even when analysis is present in other contexts, the critical failure mode is skipping the mandatory *write + re-open + validate* gate.
- latest_executor_action: Treat artifact emission as a hard stop (do not terminate until it passes). Before termination, always:
  1) Derive `sample_ids` per task policy (here: target fps=5; if video fps unknown/0, fall back to a conservative stride but still produce outputs).
  2) Produce labels for every sampled frame and write `/root/pred_instructions.json` with strict interval keys `"{fid}->{fid+1}"`, values as **non-empty lists** of strings from the allowed label set.
  3) Produce one mask per sampled frame and write `/root/pred_dyn_masks.npz` containing `shape` and per-frame CSR triplets keyed by the **true frame id** (`f_{fid}_data/indices/indptr`) for every `fid` in `sample_ids` (write all-false masks when uncertain rather than skipping).
  4) Re-open both files from disk and validate existence, JSON parseability, NPZ loadability, full key coverage over `sample_ids`, and CSR invariants (`len(indptr)==H+1`, `indptr[-1]==indices.size`, indices within `[0,W)`). If any check fails, fix the root cause and re-write; only then terminate.
- remedy_log:
  - iter_0 | diagnosis: run produced no outputs at all; required JSON and NPZ files were not created
            | patch: (none yet; to be applied) strengthen/introduce a mandatory deliverables gate in output-validation to force write+verify of both artifacts
  - iter_1 | diagnosis: executor terminated without invoking any pipeline skills; no `/root/pred_instructions.json` or `/root/pred_dyn_masks.npz` were written
            | patch: (none yet; to be applied) enforce that the executor must run the pipeline + deliverables gate before end_turn; consider adding an explicit “do not end_turn until files exist on disk” rule
