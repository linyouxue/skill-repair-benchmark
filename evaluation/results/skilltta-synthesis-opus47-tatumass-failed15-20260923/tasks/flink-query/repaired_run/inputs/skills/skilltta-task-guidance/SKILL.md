---
name: skilltta-task-guidance
description: Task-specific operational guidance synthesized at test time from retrieved training examples.
---

# SKILL.md

## When to use
Use this skill when implementing a Flink (Java) streaming/batch job on a skeleton project that ingests gzipped CSV event data (e.g., cluster-trace-style task and job events) and must emit per-key aggregates derived from event-time session windows. The target contract typically requires:
- Reading two related gzipped CSV inputs (task events + job events) whose paths, schemas, and units (e.g., microseconds) must be discovered from provided documentation files in the workspace before coding.
- Grouping task activity by a key (e.g., jobId), sessionizing by an inactivity gap defined on event time, counting a specific event type only (e.g., SUBMIT), and reducing to one output per key gated on a lifecycle signal (e.g., job finished) from the second stream.
- Writing plain-text tuple lines to a local output file path passed as a parameter, without altering the provided class name, package, `pom.xml`, or `AppBase` contract.

Before writing code, gather:
1. Column indices and enum codes from the schema docs (`format.pdf`, `ClusterData2011_2.md`) — do not guess event-type integers.
2. Time unit (microseconds here) and how to convert to Flink's expected millisecond timestamps.
3. The `AppBase` class signature to know what datatype classes and methods must exist under `clusterdata.datatypes`.
4. Whether inputs are bounded files (batch/streaming source choice) and how gz decoding is handled.

## Possible Failure Modes
- Hardcoding event-type codes (SUBMIT, FINISH, etc.) incorrectly instead of reading them from the schema doc.
- Treating timestamps as milliseconds when the dataset is microseconds → session gaps become 1000× wrong.
- Using processing time or ingestion time instead of event-time watermarks, so session windows never fire deterministically on bounded input.
- Counting all task events instead of only SUBMIT events; or deduplicating resubmissions when the spec says re-submits after fail/evict must be counted separately.
- Emitting output before the job's finish event is observed, or emitting for jobs that never finish.
- Wrong output format: writing CSV, JSON, `Tuple2.toString()` default (`(a,b)` vs `a,b`), extra whitespace, or headers. The grader expects exactly `(jobId,count)` one per line.
- Renaming the main class, changing the package path, or editing `pom.xml`, breaking the build/run harness.
- Missing `clusterdata.datatypes` POJO classes (or missing no-arg constructor / public fields) causing Flink serialization to fall back to Kryo or fail.
- Not closing/flushing the sink, or using a parallel file sink that produces a directory of part files when a single file path is expected.
- Watermark strategy with insufficient out-of-orderness causing sessions to close prematurely or never; or forgetting to assign timestamps at all.
- Joining/coordinating the two streams incorrectly (e.g., using a regular join with windows) when a keyed connect + state (or broadcast of finished jobIds) is more appropriate.

## Possible procedures
1. Read the schema docs first. Record: field order for task_events and job_events, the integer code for SUBMIT and for the terminal job event(s) meaning "finished," and confirm the time-unit is microseconds.
2. Implement `TaskEvent` and `JobEvent` POJOs in `clusterdata.datatypes` with public no-arg constructors and public fields (or getters/setters) for the fields you use; keep them minimal.
3. Build two sources from the gzipped CSV paths. Prefer a text file source (Flink auto-decompresses `.gz`) → map lines to POJOs, filtering malformed/missing rows.
4. Assign event-time timestamps by converting microseconds → milliseconds (`ts / 1000`). Use a bounded-out-of-orderness watermark strategy; for bounded files, a monotonic or small bounded strategy is fine.
5. On the task stream: filter to SUBMIT events only, key by jobId, apply an event-time session window with a 10-minute gap, and aggregate a count per window. Do not dedupe; each SUBMIT contributes one.
6. Per job, reduce sessions to the max count. Options:
   - Key by jobId after windowing and use a `KeyedProcessFunction` that keeps the running max in state.
   - Or aggregate all session counts and take max via a second keyed reduce.
7. Gate emission on job completion: from the job event stream, filter to the terminal/finished events, key by jobId, and `connect` with the per-job max stream. In a `CoProcessFunction`/`KeyedCoProcessFunction`, store the current max in state; when the finish event arrives (or vice versa), emit `(jobId, max)` exactly once and clear state.
8. Sink: format output as the literal string `(jobId,count)` per record and write to the `output` path. Use a sink that writes a single file (e.g., `writeAsText` with parallelism 1 on the sink, or a `FileSink` configured to a single file). Ensure `env.execute()` runs and flushes.
9. Match `AppBase` conventions for parsing `--task_input`, `--job_input`, `--output` parameters exactly as the skeleton expects.
10. Recovery checks: if the output is empty, verify watermarks advance (bounded source should emit MAX_WATERMARK on close); if counts look off by 1000×, re-check microsecond conversion; if some jobs missing, verify the finished-event filter code matches the doc.

## Verification Checklist
- [ ] `LongestSessionPerJob` class name, package, and `pom.xml` are unchanged; `mvn package` (or the build the harness uses) succeeds and produces the jar name declared in `pom.xml`.
- [ ] `clusterdata.datatypes` contains the task/job event POJOs referenced by `AppBase` with public no-arg constructors.
- [ ] Event-time is derived from the CSV timestamp field, converted from microseconds to milliseconds, with a watermark strategy that allows bounded source completion.
- [ ] Only SUBMIT task events are counted; resubmissions after fail/evict are each counted (no dedup by taskId).
- [ ] Session gap is exactly 10 minutes of event-time inactivity.
- [ ] One output line per finished job, in the exact literal form `(jobId,count)` — no header, no quotes, no spaces, no trailing commas.
- [ ] Output is written to the `output` parameter path as a single file readable line-by-line; parallelism-1 sink or equivalent.
- [ ] Jobs that never finish in the input do not appear in output; jobs that finish appear exactly once.
- [ ] No content, ids, numeric codes, file names, or field orders were copied from unrelated retrieved examples; all schema-specific values come from the workspace docs.
- [ ] Untouched files (`pom.xml`, `AppBase`, other provided sources) are byte-identical.
- [ ] Recovery: on empty or malformed output, re-check (a) event-type code mapping, (b) microseconds→millis conversion, (c) watermark advancement on bounded input, (d) finish-event join emitting on both arrival orders.
