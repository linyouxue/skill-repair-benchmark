### [paper-anonymizer] Wrong output location produced (saved to CWD instead of /root/redacted)
- signal: failure
- pattern: deliverable-enforcement-and-output-verification
- anchor: deliverable-enforcement
- gap: Despite the presence of L2 guidance under `## Deliverable enforcement (do this before ending)` (and the L3 procedure in `references/deliverable-enforcement.md`), the executor still wrote `paper1.pdf`, `paper2.pdf`, `paper3.pdf` into the current working directory and ended without confirming that `/root/redacted/paper{1-3}.pdf` existed. This indicates the “enumerate exact required output paths early → pass absolute path to save/export → gate termination on `exists + non-empty + openable` at the required location” loop is not being executed at runtime.
- proposed_change: Strengthen the `deliverable-enforcement` anchor to be harder to miss and more execution-binding: (1) add an explicit rule that the current working directory is irrelevant and defaults are forbidden (“never save to relative paths; always provide the required absolute output path string”); (2) add a minimal bash gate snippet the executor can run verbatim (`mkdir -p /root/redacted; ls -l /root/redacted/paper{1-3}.pdf; python -c 'import fitz; ...' /root/redacted/paper{1-3}.pdf`) and require it before termination; (3) optionally add a “delete misplaced outputs in CWD” step to prevent confusing inventories (e.g., remove `./paper*.pdf` if the required path is `/root/redacted/...`).

## WORKFLOW-THEMES

- (none this iteration)
