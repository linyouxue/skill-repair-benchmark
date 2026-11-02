# Evidence map

- `repair/`: essential local repair records plus an exact reference to the complete public repair archive.
- `final_runs/run_01` to `run_03`: three independent executions of the identical frozen Skill on the original 22 receipts. Each directory includes configuration, request, full ACP trajectory, losslessly gzipped full LLM trajectory, actual `artifacts/stat_ocr.xlsx`, original verifier files, offline rescore, timing and audit.
- `invalid_attempts/`: an uncounted Docker collision retained for completeness.
- `execution_adapter/`: the execution adapter snapshot, group-2 preparation receipt, test, and reproducible command pattern used for the held-out task root.
- `metadata/`: credential-scan report and SHA-256 manifest for this submission.

The `offline-rescore.json` files are deterministic verifier replays over the untouched Excel artifacts. They do not replace the original verifier outputs.

