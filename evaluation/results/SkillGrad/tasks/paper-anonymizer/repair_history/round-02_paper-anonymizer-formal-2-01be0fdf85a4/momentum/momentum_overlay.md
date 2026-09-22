### [paper-anonymizer] Wrong output path used (files saved to CWD instead of `/root/redacted/...`)
- signal: failure
- pattern: deliverable-enforcement-and-output-verification
- anchor: deliverable-enforcement
- gap: The run produced `paper1.pdf`, `paper2.pdf`, `paper3.pdf` in the current working directory, indicating the executor relied on default/local filenames in the final save/export step(s) and/or never created `/root/redacted`. It also ended without a gating check that `/root/redacted/paper{1-3}.pdf` exist and are valid PDFs.
- proposed_change: Strengthen the L2 `Deliverable enforcement (do this before ending)` section to explicitly require (a) enumerating the exact required absolute output paths up front, (b) `mkdir -p` the parent directory, (c) passing those absolute paths into every `doc.save(...)` / writer call, and (d) running a final filesystem + openability verification on the required paths before termination (pointer remains to references/deliverable-enforcement.md; add an example snippet showing `/root/redacted/paper{i}.pdf` path construction).

## WORKFLOW-THEMES

- (none this iteration)
