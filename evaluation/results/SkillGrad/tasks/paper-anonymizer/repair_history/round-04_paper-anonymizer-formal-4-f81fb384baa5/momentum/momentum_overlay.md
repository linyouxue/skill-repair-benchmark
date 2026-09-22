### [paper-anonymizer] outputs not written to required `/root/redacted/` directory
- signal: failure
- pattern: deliverable-enforcement-and-output-verification
- anchor: deliverable-enforcement
- gap: Despite an existing L2 section (`Deliverable enforcement (do this before ending)`) and an L3 procedure (`references/deliverable-enforcement.md`), the executor still wrote outputs to default/local filenames (`paper1.pdf`, `paper2.pdf`, `paper3.pdf`) instead of passing the required absolute output paths (`/root/redacted/paper{1-3}.pdf`) into the save calls and gating termination on existence at those exact paths. This suggests the deliverable gate is either not being invoked at all, or is being applied abstractly ("I saved the files") without a concrete filesystem verification at the required paths.
- proposed_change: Strengthen the L2 `deliverable-enforcement` section to force an explicit mapping from inputs to exact output paths and a mandatory shell/Python verification gate that uses those exact absolute paths. Concretely: (1) add a snippet that constructs `outputs = ["/root/redacted/paper1.pdf", ...]` and requires `mkdir -p /root/redacted`; (2) require a final terminal command `ls -l /root/redacted/paper{1-3}.pdf` (and optionally `python -c 'import fitz; ...'`) before ending; (3) explicitly warn that `cd`/current working directory is irrelevant—only the output path argument controls save location; (4) recommend deleting misplaced `./paper*.pdf` outputs to avoid confusion.

## WORKFLOW-THEMES

- (none this iteration)
