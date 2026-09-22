### [data-to-d3] Output path contract violated (/root/output vs ./output)
- signal: failure
- pattern: materialize-required-deliverables-before-end
- anchor: deliverables-first-workflow
- gap: The run created the web app artifacts under a project-relative `output/...` directory, but the task contract (and verifier) requires the deliverables to exist at absolute paths under `/root/output/...`. Because the executor did not treat the absolute output inventory as authoritative and did not perform a pre-end existence check on the exact required paths (e.g., `test -f /root/output/index.html`), the verifier interpreted the deliverables as missing.
- proposed_change: Patch the L2 “Deliverables-first workflow” section to explicitly say: when the task specifies absolute destinations like `/root/output/...`, do not write to `./output`, `dist/`, or other substitutes; write to those exact absolute paths. Add/strengthen the pointer to `references/deliverables-checklist.md` with an explicit mandatory final verification step that checks existence and non-empty size of each required absolute path before end_turn.

## WORKFLOW-THEMES

- (none this iteration)
