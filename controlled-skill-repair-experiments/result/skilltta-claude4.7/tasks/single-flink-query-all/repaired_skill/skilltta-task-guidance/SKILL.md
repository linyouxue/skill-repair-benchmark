---
name: skilltta-task-guidance
description: Guidance for implementing the LongestSessionPerJob Flink job over Google cluster traces
---

# Task Guidance: Longest Stage Per Finished Job

## Goal
Implement `clusterdata.query.LongestSessionPerJob` (Flink DataStream job) that, for each **finished** job, emits `(jobId, maxTasksInLongestStage)` where a *stage* is a run of task SUBMIT events for that job separated by < 10 minutes of inactivity.

## Inputs & Schema (Google cluster-usage trace, 2011_2)
Read `data/format.pdf` + `data/ClusterData2011_2.md`. All files are gzipped CSV (no header). Timestamps are in **microseconds**.

### Task events CSV columns (relevant):
- `0` timestamp (μs)
- `2` job_id (long)
- `3` task_index (long)
- `5` event_type (int)

### Job events CSV columns (relevant):
- `0` timestamp (μs)
- `2` job_id
- `3` event_type

### Event-type codes (common to both streams)
`0=SUBMIT, 1=SCHEDULE, 2=EVICT, 3=FAIL, 4=FINISH, 5=KILL, 6=LOST, 7=UPDATE_PENDING, 8=UPDATE_RUNNING`.

## Critical Semantics (fix the two bug areas)

### (A) "Finished" job determination
> A job is considered **finished** iff a **job event** with `event_type ∈ {FINISH(4), FAIL(3), KILL(5)}` appears for its `job_id`.
- Do **not** restrict to only `FINISH==4`; the trace commonly terminates jobs with FAIL/KILL as well.
- SCHEDULE/UPDATE_* are **not** terminal.
- Terminality must be driven by the **job_events** stream, not inferred from task events.

### (B) Output eligibility
> Emit `(jobId, longestStageTaskCount)` **only for jobs whose job_events stream contains a terminal event** (per rule A).
- Jobs seen only in task_events but with no terminal job event → **do not emit**.
- Jobs with a terminal job event but zero SUBMIT task events → emit count `0` only if a SUBMIT stage existed; otherwise skip. (In practice, finished jobs always have ≥1 SUBMIT.)
- Emit **once per job** after the stream completes (bounded source: finite .gz file). Use a keyed process function with a `MapState`/`ValueState` and emit on close / watermark == +∞, or collect to a list sink and write on job close.

## Stage definition (precise)
- Consider **only task events with `event_type == 0 (SUBMIT)`**.
- Sort/process per `job_id` by event-time (timestamp μs).
- Gap threshold = **10 minutes = 600_000_000 μs**.
- A new stage begins when `currentTs - lastSubmitTs > 600_000_000`. Equal-to boundary case: treat `>` strictly as gap; `<=` keeps same stage (either is accepted but be consistent).
- Stage size = **count of SUBMIT events in that stage** (NOT distinct task_index). Resubmits of the same task after FAIL/EVICT count separately — this matches "count SUBMIT events".
- Per job, keep the **max** stage size seen.

## Recommended Flink topology
1. Two bounded sources (readTextFile on the given `.gz` paths — Flink auto-decompresses by extension).
2. Parse into POJOs under `clusterdata.datatypes`:
   - `TaskEvent {long timestamp; long jobId; long taskIndex; int eventType;}`
   - `JobEvent  {long timestamp; long jobId; int eventType;}`
   Provide public no-arg ctor + getters/setters (Flink POJO rules).
3. Filter task stream to SUBMIT only; filter job stream to terminal events only.
4. Assign event-time timestamps + watermarks (`forBoundedOutOfOrderness`, small bound — the file is batch so a large allowed lateness is fine).
5. Union the two streams (or connect) keyed by `jobId`.
6. In a `KeyedProcessFunction`:
   - State: `lastSubmitTs`, `currentStageCount`, `maxStageCount`, `finished` (boolean).
   - On SUBMIT: if `lastSubmitTs == null` or `ts - lastSubmitTs > 600_000_000` → start new stage (`currentStageCount = 1`); else increment. Update `maxStageCount = max(max, currentStageCount)`. Update `lastSubmitTs`.
   - On terminal job event: set `finished = true`.
   - On job close (use `close()` + a `ListState` collected sink, OR register a timer at `Long.MAX_VALUE` and emit in `onTimer`): if `finished && maxStageCount > 0` → emit `(jobId, maxStageCount)`.
7. Sink: write to the `output` path, one `(jobId,count)` per line in the exact format `(jobId,count)` — no spaces, parentheses included.

## Output format (exact)
```
(6253638808,3)
(6253712002,17)
```
- Parentheses, comma-separated, no spaces, one tuple per line.
- Order is not evaluated.

## Common pitfalls to avoid
- Treating only `FINISH(4)` as terminal → **misses FAIL/KILL finished jobs**. (Bug area A.)
- Emitting results for every job seen in task_events regardless of whether a job terminal event arrived. (Bug area B.)
- Counting distinct task_index instead of SUBMIT event occurrences (resubmits must count separately).
- Using processing time instead of event time for gap detection.
- Forgetting `.gz` handling — Flink's text file source handles `.gz` by filename.
- Wrong gap unit: 10 minutes = **600_000_000 microseconds** (not ms/ns).
- Changing class name or `pom.xml` — forbidden.

## Minimal checklist before running
- [ ] `TaskEvent`, `JobEvent` POJOs implemented and used by `AppBase`.
- [ ] SUBMIT filter applied on task stream.
- [ ] Terminal filter `{3,4,5}` on job stream.
- [ ] Keyed by `jobId`, event-time, 10-min gap in μs.
- [ ] Emission gated on `finished == true`.
- [ ] Output written to `output` path in `(id,count)` format.
