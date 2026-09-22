### [reserves-at-risk-calc] Wrong output path and artifact (required workbook not saved to mandated location)
- signal: failure
- pattern: save-and-verify-output-artifact
- anchor: workflow-deliver-the-required-artifact-mandatory
- gap: The executor performed a final save/export, but wrote the artifact to a non-required path/name (`data/test-rar.xlsx`) rather than the mandated absolute output `/root/output/rar_result.xlsx`. This indicates the “Deliver the required artifact (mandatory)” completion gate is not being treated as a hard constraint (no explicit Save As to exact path, and/or no post-save existence check at the required path).
- proposed_change: Strengthen the L2 section **“Workflow: Deliver the required artifact (mandatory)”** to explicitly require: (1) use the *exact absolute path + filename* from the task (not a convenient working path), (2) after saving, run an existence check specifically against that required path (and optionally re-open it) before terminating; add a short anti-pattern note like “do not leave the final file under `data/` or other workspace-relative paths unless the task requires it.”

## WORKFLOW-THEMES

- (none this iteration)
