### [azure-bgp-oscillation-route-leak] ended run without producing required /app/output/oscillation_report.json
- signal: failure
- pattern: write-required-output-artifact
- anchor: output-expectations
- gap: Agent violated the skill’s hard gate (“deliverable write + read-back verification … DO NOT end the run until the read-back verification succeeds”) by terminating (`end_turn`) without any step that writes `/app/output/oscillation_report.json` and without any subsequent read-back verification. This indicates the termination decision is not being guarded by the output checklist, even though `references/write-and-verify-output-json.md` exists.
- proposed_change: Strengthen the termination guard in L2 `## Output Expectations` to require an explicit pre-termination confirmation that (a) the file was written to the exact required path and (b) read-back verification succeeded (e.g., “state: verified /app/output/oscillation_report.json parses and has keys …”). Consider adding a very short mandatory template the executor must fill (path, required keys, verification result) and a pointer that the executor must run the L3 algorithm as the last action on any file-graded task.

## WORKFLOW-THEMES

- (none this iteration)
