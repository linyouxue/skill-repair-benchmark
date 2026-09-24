### dependency-surface-audit-before-finalize | workflow | ensure all referenced/required classes and files exist, compile, and are wired
- anchor: (none yet)
- appeared_in: iter_2
- description: When implementing a task within an existing scaffold (e.g., Flink job skeleton + shared `AppBase`), it is easy to only edit the top-level job class and forget required supporting classes (POJOs, parsers, serializers) that the scaffold expects at compile/run time. The failure mode shows up as a job that compiles incompletely or runs but produces empty/incorrect output because it cannot parse inputs or materialize the intended event-time fields. In this iteration, the output inventory contained only `LongestSessionPerJob.java` and `AppBase.java`, while the task explicitly required implementing datatype classes under `clusterdata.datatypes`.
- latest_executor_action: Before finalizing any solution that plugs into a provided framework/base class, enumerate the full dependency surface implied by: (a) imports and references in the edited file(s), (b) the base class or runner (`AppBase`), and (c) the README/task prompt (explicit required packages). Create any missing source files (e.g., `src/main/java/clusterdata/datatypes/*`) with the expected fields, constructors, getters, parsing logic, and `Serializable`/POJO conventions. Then run a local compile (e.g., `mvn -q test`/`mvn -q package`) and, if feasible, a smoke run on a small sample to confirm non-empty output with correct schema.
- remedy_log:
  - iter_2 | diagnosis: required datatype classes were not created; only top-level job and base class existed, preventing correct parsing and stage-count computation
            | patch: none (new pattern recorded)

### evidence-access-blocked-by-sandbox | workflow | diagnoser cannot attribute failure because trace/verifier artifacts are inaccessible or empty
- anchor: (none yet)
- appeared_in: iter_0
- description: When the executor/diagnoser attempts to inspect run evidence (e.g., `trace.jsonl`, verifier logs), the artifacts may be unreadable, empty, or located outside the sandbox-allowed project root. In this condition, no concrete behavioral failure can be localized to a skill mistake because there is no observable execution trace or output inventory. This is an environment/harness issue rather than a guidance or reasoning failure.
- latest_executor_action: Before proposing any skill edits or attributing failure to planning/execution, verify that (a) the harness exported a non-empty trace into the allowed project root, and (b) verifier evidence paths are accessible within sandbox constraints. If evidence is missing/inaccessible, stop diagnosis at “insufficient evidence,” and request/perform artifact relocation (copy/symlink into allowed root) or harness configuration fixes to emit logs where they can be read.
- remedy_log:
  - iter_0 | diagnosis: trace file empty and verifier evidence path escaped allowed project root, preventing localization of any earlier behavioral failure
            | patch: none (requires harness/artifact export fix, not skill text)
