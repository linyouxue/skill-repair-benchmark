### [energy-unit-commitment] Missing required /root/report.json artifact
- signal: failure
- pattern: always-emit-required-artifact
- anchor: reporting-discipline
- gap: The executor terminated at the final end_turn without running the mandatory “finalize required artifact” routine. Concretely, it never executed “write JSON exactly to /root/report.json” followed by “re-open/read and minimally validate file exists + JSON parses + required keys present”, so the output inventory contained only the input network.json and no report for the verifier to evaluate.
- proposed_change: Strengthen L2 milp-solver-workflow → Reporting Discipline with an explicit non-skippable end-of-run checklist gate (must run immediately before end_turn) and a hard requirement to call the L3 algorithm references/report-json-finalization.md whenever the evaluator requires /root/report.json. The checklist should include: write to the fixed path, re-open/parse, check required top-level keys, and only then allow termination; if solver has no incumbent, branch to a heuristic-feasible schedule and still write the artifact with solver_status indicating fallback.

## WORKFLOW-THEMES

- (none this iteration)
