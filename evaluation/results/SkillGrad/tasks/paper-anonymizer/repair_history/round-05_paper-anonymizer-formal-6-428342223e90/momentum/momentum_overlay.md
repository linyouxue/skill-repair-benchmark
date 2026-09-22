### [paper-anonymizer] misplaced output paths: PDFs saved to working directory instead of required `/root/redacted/paper{1-3}.pdf`
- signal: failure
- pattern: deliverable-enforcement-and-output-verification
- anchor: deliverable-enforcement
- gap: Despite an existing L2 rule requiring an explicit input→output contract, passing exact absolute output paths into every save/export call, and gating termination on verifying those exact paths, the executor still exported as `paper1.pdf`, `paper2.pdf`, `paper3.pdf` in the working directory and ended without confirming `/root/redacted/paper{1-3}.pdf` exist. This suggests the deliverable-enforcement step is being treated as optional/late-stage prose rather than a mandatory preflight+postflight checklist with runnable verification.
- proposed_change: Strengthen the L2 `Deliverable enforcement (do this before ending)` section to require a concrete preflight contract block that binds required outputs to variables used in *all* downstream save calls (e.g., `out_paths = ["/root/redacted/paper1.pdf", ...]` and forbid saving to any other path), plus a mandatory postflight “gate” snippet (shell `test -s` + `python -c 'import fitz; fitz.open(...)'`) that must be run before termination. Add an explicit instruction: if outputs are created elsewhere, copy/move them into the required directory and re-run the gate; optionally delete misplaced `./paper*.pdf` to prevent confusion.

## WORKFLOW-THEMES

- (none this iteration)
