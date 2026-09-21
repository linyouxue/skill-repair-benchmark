### [sec-financial-report] terminates without producing required `/root/answers.json`
- signal: failure
- pattern: required-artifact-answers-json
- anchor: plan-package-outputs
- gap: Despite an existing rule under **“Plan & Package Outputs”** (in both `13f-analyzer` and `fuzzy-name-search`) stating “Do not terminate until deliverables are written at the exact required paths” and “serialize once, then re-open and parse,” the executor still performed `end_turn` without writing (or schema-validating) `/root/answers.json`. The first observable failure is the missing artifact at the verifier-expected path.
- proposed_change: Strengthen the L2 **Plan & Package Outputs** section into an explicit hard stop: add a termination gate checklist (path + required keys + write + read-back parse + existence check) and reference `references/required-artifacts-answers-json.md` as mandatory to run whenever the prompt requires `/root/answers.json`. Consider adding a final-step snippet the executor can copy-paste that writes and then verifies keys `q1_answer..q4_answer` before termination.

## WORKFLOW-THEMES

- (none this iteration)
