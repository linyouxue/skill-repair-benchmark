### [sec-financial-report] Missing required /root/answers.json because executor terminated without running the packaging gate
- signal: failure
- pattern: required-artifact-answers-json
- anchor: plan-package-outputs
- gap: The run ended (`end_turn`) without writing `/root/answers.json`. Although both `13f-analyzer` and `fuzzy-name-search` skills contain a hard-stop “Plan & Package Outputs” terminal sentinel (`write_verify_and_gate(...)`), execution never invoked the skills at all (`n_skill_invocations: 0`), so the safeguard was not applied.
- proposed_change: Strengthen the `plan-package-outputs` guidance to include an explicit rule: when a required `answers.json` artifact is present, the executor must *ensure the sentinel runs*—either by invoking the relevant skill section or by reproducing the exact `write_verify_and_gate(required_path, payload, required_keys)` procedure in the main flow immediately before termination. Add a “no-skill-invocation” fallback note: if tools/skills were not invoked during the run, still run the packaging gate as the final must-do step.

## WORKFLOW-THEMES

- (none this iteration)
