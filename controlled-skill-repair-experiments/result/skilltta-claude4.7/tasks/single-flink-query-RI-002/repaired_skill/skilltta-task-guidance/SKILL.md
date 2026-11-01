---
name: skilltta-task-guidance
description: Temporary guidance for implementing the Flink LongestSessionPerJob task over Google cluster-usage traces
---

# Task Guidance: LongestSessionPerJob (Flink)

## Problem Restatement
For each **finished** job, identify "stages" from its task SUBMIT events. A stage is a run of SUBMIT events separated by < 10 minutes of inactivity (in event time). Report the task count of the job's largest stage.

## Critical Correctness Rules (derive from the spec, not assumptions)

### Rule A — Output qualification: only FINISHED jobs
The spec says "once the job has finished". **Do not emit a tuple for every jobId that appears in task events.** You must:
1. Read the job-events stream and detect job completion (Google traces job event types: 0=SUBMIT, 1=SCHEDULE, 2=EVICT, 3=FAIL, 4=FINISH, 5=KILL, 6=LOST; treat FINISH/FAIL/KILL per the format doc — confirm by reading `format.pdf` / `ClusterData2011_2.md`; the spec wording "finished" typically means event type 4 FINISH).
2. Only output `(jobId, maxStageTaskCount)` for jobs whose job-event stream contains a terminal/finish event.
3. A job that has task events but never finishes in the input window **must not appear** in the output.

Implementation sketch: keep per-job stage state keyed by jobId from the task stream, and gate emission on a signal from the job stream (e.g., connect the two streams via `connect` + `KeyedCoProcessFunction`, or union with a tagged type).

### Rule B — Only SUBMIT task events count
Filter task events to event type `SUBMIT` (type 0) before stage logic. Resubmits (SUBMIT after FAIL/EVICT) **are counted as new tasks within whatever stage they land in** — do not dedupe by taskIndex.

### Rule C — Timestamps are microseconds
- 10 minutes = `10 * 60 * 1_000_000L` microseconds.
- Assign event-time timestamps and watermarks in microseconds (don't silently convert to ms).

### Rule D — Stage boundary = 10-min gap of SUBMITs for that job
Use event-time session windowing per jobId with a 10-minute gap, counting records per window. Then reduce to the max count per jobId. Options:
- `keyBy(jobId).window(EventTimeSessionWindows.withGap(Time.minutes(10)))` with a count aggregator, then keyBy jobId again and keep max.
- Or manual `KeyedProcessFunction` with a timer at `lastSubmitTs + 10min` that flushes the current stage count into a running max.

## Output Format
- One line per finished job: `(jobId,maxCount)` — literal parentheses, comma separated, no spaces.
- Order does not matter.
- Write to the local path given by `output` parameter. Use `StreamingFileSink` with a single-file sink or (simpler for batch-style CSV input) collect results and write via `PrintSink`/`writeAsText` to `output` with parallelism 1 to avoid directory output.

## Required Data Classes (under `clusterdata.datatypes`)
Implement at minimum:
- `TaskEvent` with fields: `timestamp` (long, μs), `jobId` (long), `taskIndex` (long/int), `eventType` (int), plus any required by `AppBase`.
- `JobEvent` with fields: `timestamp` (long, μs), `jobId` (long), `eventType` (int).
Provide no-arg constructors + public fields or getters (POJO) so Flink serializes efficiently.

## Parsing Pattern (transferable from CSV examples)
From the retrieved CSV-processing patterns:
- Treat each gzipped CSV as newline-delimited rows; split by `,`; index into fields per `format.pdf`.
- Guard against empty/short lines (skip).
- Parse ints/longs with try/catch; drop malformed rows (don't crash the job).
- Reading `.gz`: use `TextInputFormat` on the `.gz` path (Flink auto-decompresses), or `env.readTextFile(path)`.

## Suggested Pipeline
1. `taskStream = env.readTextFile(task_input).map(parseTaskEvent).filter(eventType==SUBMIT).assignTimestampsAndWatermarks(...μs...)`.
2. `jobFinishStream = env.readTextFile(job_input).map(parseJobEvent).filter(isTerminal).assignTimestampsAndWatermarks(...)`.
3. Session-window task stream by jobId with 10-min gap → `(jobId, stageCount)`.
4. KeyBy jobId → reduce to max stage count per job (keyed state).
5. Connect with `jobFinishStream` keyed by jobId; on finish signal, emit `(jobId, currentMax)` and clear state.
6. Sink with parallelism 1 to `output` path, formatting as `(jobId,count)`.

## Common Pitfalls to Avoid
- ❌ Emitting a line per jobId seen in task events (fails Rule A — the location hint flags exactly this).
- ❌ Using processing time or Time.minutes assumed to be ms when ts is μs.
- ❌ Counting non-SUBMIT task events.
- ❌ Deduping resubmits of the same taskIndex.
- ❌ Writing to `output` as a directory via default `writeAsText` with parallelism>1.
- ❌ Changing the class name `LongestSessionPerJob` or editing `pom.xml`.

## Verification Before Finishing
- Jar builds via provided `pom.xml`.
- Running with the sample paths produces a file at `output` where every line matches `^\(\d+,\d+\)$`.
- Every jobId in output has a terminal event in `job_input`; jobIds without one are absent.
