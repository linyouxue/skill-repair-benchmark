### [drone-planning-control] evidence/skill paths guessed or outside sandbox, blocking grounded diagnosis
- signal: failure
- pattern: evidence-access-before-domain-changes
- anchor: workflow-access-evidence-inside-the-sandbox
- gap: The executor tried to read a hardcoded verifier filename (`.../verifier/evidence.json`) that did not exist, instead of enumerating verifier/results directories to discover available artifacts. It then attempted to read skill content via an absolute path that was blocked for “escaping the allowed project root”. This prevents accessing the verifier’s actual failing command(s)/metrics and breaks the required sandbox-relative evidence workflow.
- proposed_change: Strengthen L2 "Workflow: Access evidence inside the sandbox" (in all relevant skills) to be more fail-fast and explicit: (1) forbid guessing filenames like `evidence.json`; require `list_dir`/directory enumeration of verifier/results, then open the present artifacts; (2) add an explicit branch for “escapes allowed project root”: do not retry with different absolute paths—copy/move artifacts under the sandbox root and proceed with relative paths; (3) mandate stopping domain edits until evidence is successfully loaded and parsed.

## WORKFLOW-THEMES

- (none this iteration)
