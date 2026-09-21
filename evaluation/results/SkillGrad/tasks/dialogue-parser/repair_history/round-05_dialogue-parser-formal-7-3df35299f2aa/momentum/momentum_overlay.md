### [dialogue-parser] run ended without producing required /app/dialogue.json and /app/dialogue.dot artifacts
- signal: failure
- pattern: always-write-required-artifacts
- anchor: plan-the-run-minimal
- gap: Despite the L2 hard stop (“immediately before `end_turn`, run export → artifact check … Do not call `end_turn` until you have re-opened the required files and confirmed they load/parse.”), the run terminated without any export/write actions and without an artifact existence/non-empty/reload check; the output inventory contained only `script.txt`.
- proposed_change: Strengthen L2 `Plan the run (minimal)` end-of-run guardrail into a mandatory, explicit checklist the executor must state and complete immediately before `end_turn` (name both required paths), and add a requirement to *log* the artifact-check results (exists, size>0, `json.load` succeeds, DOT begins with `digraph`). If this still recurs, add a dedicated L3 “end-turn hard gate” mini-procedure that the executor must invoke whenever filesystem deliverables are required.

## WORKFLOW-THEMES

- (none this iteration)
