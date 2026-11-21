# Controlled55 GPT-5.2 Results

This compact delivery contains the final frozen Skills and selected evidence for the completed Controlled55 experiment. The original audit directory is preserved unchanged.

## Layout

- `skills/`: final selected Skill bundle for each of the 22 repair trials.
- `summary/`: completion marker, fixed experiment configuration, recovery baseline, and the 55-run result summary.
- `evidence/repair-generation/`: compact candidate-generation metadata for each repair trial.
- `evidence/selected-runs/`: selected `RUN_RECORD.json`, `result.json`, and available verifier outputs for 22 repairs and 33 controls.
- `manifests/`: candidate selection, selected-run provenance, original audit paths, and SHA-256 checksums.

The full BenchFlow trajectories and prepared workspaces are intentionally not duplicated here; their original paths are recorded in `manifests/audit-paths.json`.
