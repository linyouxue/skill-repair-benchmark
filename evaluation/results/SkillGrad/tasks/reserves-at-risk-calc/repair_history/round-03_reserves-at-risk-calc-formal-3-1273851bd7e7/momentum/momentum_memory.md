### save-and-verify-output-artifact | workflow | executor ends run without saving required workbook to specified output path
- anchor: workflow-deliver-the-required-artifact-mandatory
- appeared_in: iter_0, iter_1
- description: For spreadsheet tasks, the executor may complete analysis or edits in-memory but terminate without persisting the required artifact (e.g., an .xlsx workbook) to the exact output path/filename demanded by the task. This produces an empty output inventory and fails the task at the first externally observable checkpoint. The mechanism is a missing end-of-run “persistence + existence verification” step (Save/Export, then confirm file presence or re-open).
- latest_executor_action: Treat saving as a hard requirement gated by a completion checklist. Before ending: (1) write/save the workbook to the exact required output path and filename, (2) verify persistence by checking the file exists at that path (and ideally re-open to confirm), and (3) only then terminate. If save fails or path mismatches, retry with corrected path until verification passes.
- remedy_log:
  - iter_0 | diagnosis: run produced no output file; agent terminated without executing/finishing “Save As/export workbook to required path”
            | patch: (none yet; record created from diagnosis)
  - iter_1 | diagnosis: required deliverable /root/output/rar_result.xlsx missing; terminal end_turn occurred without any save/export + existence check
            | patch: (none yet; diagnosis mapped to existing SKILL.md completion gate; no new patch proposed beyond reinforcing use of that rule)

### verifier-evidence-path-allowlist | workflow | diagnoser cannot access verifier evidence due to path allowlist / missing in-root artifacts
- anchor: (none yet)
- appeared_in: iter_2
- description: The diagnoser attempts to read verifier evidence (e.g., `.../verifier/evidence.json`) using paths that either do not exist or are outside the sandbox/project-root allowlist, causing file-not-found or “escapes the allowed project root” errors. This prevents identifying the first spreadsheet mistake, so proposing edits to the spreadsheet skill would be speculative.
- latest_executor_action: When verifier evidence is needed, only search/read within the allowed project root (the rollout/batch directory). If the expected evidence path is missing, enumerate plausible in-root verifier artifact filenames (e.g., `verifier/*.json`, `verifier/results.json`, `verifier/report.txt`, `assessment.json`) and fall back to those. If none are readable, explicitly classify the issue as a harness/evidence-collection constraint and avoid recommending domain-skill changes.
- remedy_log:
  - iter_2 | diagnosis: attempted read of `/.../verifier/evidence.json` returned not found; subsequent attempt to read verifier directory blocked by sandbox allowlist (“escapes the allowed project root”)
            | patch: (none yet; new workflow rule needed for evidence discovery within allowed root)
