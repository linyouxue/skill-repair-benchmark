### [syzkaller-ppdev-syzlang] missed required syzlang/const file creation (empty output inventory)
- signal: failure
- pattern: deliverables-presence-check
- anchor: deliverables-gate-write-verify-required-output-files
- gap: The trajectory never performs the essential file-write operations to add the required syzlang artifacts (e.g., `dev_ppdev.txt` and `dev_ppdev.txt.const`) into the syzkaller `sys/linux/` tree. As a result, the verifier sees an empty output inventory: “No required syzlang/const files were created/modified”. The executor likely did non-artifact work (planning/build thinking), but skipped the blocking “create stubs first” gate.
- proposed_change: Strengthen the L2 “Deliverables gate: create stubs first, then iterate” rule to be an explicit *blocking precondition* before any build-loop steps: within the first 1–2 tool calls, `mkdir -p sys/linux` (as needed) and write minimal stubs for every required file at the exact paths; then run `ls -l`/`sed` checks. Add an explicit stop condition: if the stub files are not present/non-empty, do not run `make descriptions`/triage; only perform file creation/writes until the gate passes.

## WORKFLOW-THEMES

- (none this iteration)
