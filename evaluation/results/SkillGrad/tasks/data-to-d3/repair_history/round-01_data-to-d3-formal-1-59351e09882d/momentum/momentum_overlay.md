### [data-to-d3] missing artifact generation: no files written to required /root/output paths
- signal: failure
- pattern: materialize-required-deliverables-before-end
- anchor: (none yet)
- gap: The agent terminated at the finalization step (end_turn) without writing any output artifacts; required deliverables like `/root/output/index.html` and supporting `/root/output/js/...`, `/root/output/css/...`, `/root/output/data/...` were never created/copied.
- proposed_change: Add an L2 workflow rule to SKILL.md (e.g., a new section "Deliverables checklist before finish") requiring: (1) create required directory structure, (2) copy input data into the output data folder preserving subfolders, (3) write HTML/CSS/JS plus vendored d3 file to specified locations, and (4) verify existence + non-empty size of each required path before end_turn.

## WORKFLOW-THEMES

- (none this iteration)
