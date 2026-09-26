### [drone-planning-control] Missing verifier/trace evidence prevents grounded diagnosis of which success criterion failed
- signal: failure
- pattern: evidence-access-before-domain-changes
- anchor: workflow-access-evidence-inside-the-sandbox
- gap: The run’s post-execution inspection step could not proceed because it tried to read non-existent/incorrect verifier evidence paths ("expected verifier evidence JSON is absent") and the trace file was empty, leaving no actionable evidence to attribute failure to steady-state error vs overshoot vs accel-limit vs per-timestep tracking error. The skill says to prefer relative paths and stop if evidence cannot be accessed, but it does not explicitly require enumerating the verifier/results directory to discover actual filenames instead of guessing (e.g. `evidence.json`).
- proposed_change: Patch the shared L2 section "Workflow: Access evidence inside the sandbox" (present across skills) to add an explicit branch: (1) if a referenced trace/evidence file is missing/empty, list the verifier/results output directory tree to discover available artifacts; (2) load/parse whichever evidence exists; (3) if still missing, fail fast and treat as artifact-location/harness issue (copy artifacts into sandbox root if needed) before any controller/planner edits.

## WORKFLOW-THEMES

- (none this iteration)
