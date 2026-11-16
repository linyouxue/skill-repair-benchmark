# JPG adapter changes used by this experiment

1. The diagnosis adapter loads the published 37-window package, validates 22 image blocks per window, converts image data URLs into Anthropic Messages image blocks for Tatu, and saves the exact provider-shaped request before delivery plus the complete response afterward.
2. A resumed run may reuse an explicitly named diagnosis source run. The consuming run records the external cache source and carries forward the full diagnosis samples, merge record, and window coverage.
3. Only the native runnable JPG task components (`task.md`, `environment/`, `oracle/`, and `verifier/`) enter BenchFlow. Package documentation, offline `tests/`, result templates, and generalization fixtures are excluded from the runtime task view.
4. The configured 65 parent-iteration limit is passed through the public executor, OpenHands adapter, ACP outcome validation, persisted config, and normalized result validation.
5. A frozen JPG final execution copies the actual `/app/workspace/stat_ocr.xlsx` into the host-mounted rollout artifact directory before verification and writes its SHA-256 receipt.
6. The bounded edit path rejects malformed replacement fields instead of treating a missing replacement body as an empty deletion.

The corresponding source snapshot is under `code/`; exact commands are under `commands/`.
