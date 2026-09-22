### save-and-verify-output-artifact | workflow | executor ends run without saving required workbook to specified output path
- anchor: workflow-deliver-the-required-artifact-mandatory
- appeared_in: iter_0, iter_1, iter_3, iter_4
- description: For spreadsheet tasks, the executor may complete analysis or edits in-memory but terminate without persisting the required artifact (e.g., an .xlsx workbook) to the exact output path/filename demanded by the task. This produces an empty output inventory or a missing/undiscoverable deliverable and fails the task at the first externally observable checkpoint. The mechanism is a missing end-of-run “persistence + existence verification” step (Save/Export, then confirm file presence or re-open). A common variant is saving an intermediate/working file under a convenient relative path (e.g., under `data/`) rather than the mandated absolute `/root/output/...` location.
- latest_executor_action: Treat saving as a hard requirement gated by a completion checklist. Before ending: (1) extract the exact required output path + filename from the task instructions, (2) perform an explicit Save As/export to that exact location/name (create parent dirs if needed), (3) verify persistence by checking the file exists at that path (and ideally re-open to confirm it is the final edited workbook), and (4) only then terminate. If save fails or path mismatches, retry with corrected path until verification passes.
- remedy_log:
  - iter_0 | diagnosis: run produced no output file; agent terminated without executing/finishing “Save As/export workbook to required path”
            | patch: (none yet; record created from diagnosis)
  - iter_1 | diagnosis: required deliverable /root/output/rar_result.xlsx missing; terminal end_turn occurred without any save/export + existence check
            | patch: (none yet; diagnosis mapped to existing SKILL.md completion gate; no new patch proposed beyond reinforcing use of that rule)
  - iter_3 | diagnosis: workbook was saved/exported, but to the wrong path/name (`data/test-rar.xlsx`) instead of the mandated `/root/output/rar_result.xlsx`
            | patch: (none yet; reinforce L2 completion gate to emphasize absolute path + post-save exists check)
  - iter_4 | diagnosis: required deliverable `/root/output/rar_result.xlsx` missing; output inventory shows only `data/test-rar.xlsx`, indicating final save/export happened to a non-required path and the run ended without an existence check at the mandated path
            | patch: (none yet; recommend strengthening the completion gate with an explicit “stop-the-world” existence check + retry loop keyed on the exact absolute required path)

### verifier-evidence-path-allowlist | workflow | diagnoser cannot access verifier evidence due to path allowlist / missing in-root artifacts
- anchor: evidence-discovery-is-root-scoped-diagnosis
- appeared_in: iter_2
- description: The diagnoser attempts to read verifier evidence (e.g., `.../verifier/evidence.json`) using paths that either do not exist or are outside the sandbox/project-root allowlist, causing file-not-found or “escapes the allowed project root” errors. This prevents identifying the first spreadsheet mistake, so proposing edits to the spreadsheet skill would be speculative.
- latest_executor_action: When verifier evidence is needed, only search/read within the allowed project root (the rollout/batch directory). If the expected evidence path is missing, enumerate plausible in-root verifier artifact filenames (e.g., `verifier/*.json`, `verifier/results.json`, `verifier/report.txt`, `assessment.json`) and fall back to those. If none are readable, explicitly classify the issue as a harness/evidence-collection constraint and avoid recommending domain-skill changes.
- remedy_log:
  - iter_2 | diagnosis: attempted read of `/.../verifier/evidence.json` returned not found; subsequent attempt to read verifier directory blocked by sandbox allowlist (“escapes the allowed project root”)
            | patch: (none yet; new workflow rule needed for evidence discovery within allowed root)
