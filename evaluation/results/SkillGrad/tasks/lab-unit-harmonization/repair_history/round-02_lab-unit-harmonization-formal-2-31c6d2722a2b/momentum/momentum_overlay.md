### [lab-unit-harmonization] missing required output artifact (`/root/ckd_lab_data_harmonized.csv`)
- signal: failure
- pattern: persist-required-deliverables
- anchor: step-4-persist-deliverable-post-save-verification
- gap: Despite SKILL.md explicitly containing **“Step 4: Persist Deliverable + Post-save Verification”** (with `df.to_csv(out_path, index=False)` and a round-trip `pd.read_csv(out_path)` assertion), the attempt terminated (end_turn) without any observable write-to-disk step, so the verifier had no CSV to validate.
- proposed_change: Strengthen/clarify the L2 Step 4 completion gate language so it is treated as non-optional: “do not call end_turn until the file exists at the exact required path, is non-empty, and successfully round-trips with schema preserved.” Add a micro-checklist in Step 4 (path must match exactly; `exists && size>0`; reload; columns match) and suggest placing this immediately before termination.

## WORKFLOW-THEMES

- (none this iteration)
