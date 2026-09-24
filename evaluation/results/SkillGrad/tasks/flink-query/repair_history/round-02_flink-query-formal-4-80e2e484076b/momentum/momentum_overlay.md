### [flink-query] Missing required datatype/supporting classes; only top-level job file was produced
- signal: failure
- pattern: dependency-surface-audit-before-finalize
- anchor: (none)
- gap: The executor delivered only `LongestSessionPerJob.java` (and existing `AppBase.java`) but did not create the required task/job event datatype classes under `clusterdata.datatypes`. The task prompt explicitly required implementing these classes; without them the pipeline cannot parse inputs / extract timestamps / compute stage counts, leading to empty or incorrect output.
- proposed_change: Add an L2 workflow step (or a short “pre-submit checklist”) to force a dependency-surface audit: enumerate all referenced packages/types from the job + base class; create missing POJOs/parsers in `src/main/java/clusterdata/datatypes/*` with required fields and parsing; run `mvn -q package` and ensure the job produces non-empty output on a smoke input before finalizing.

## WORKFLOW-THEMES

- (none this iteration)
