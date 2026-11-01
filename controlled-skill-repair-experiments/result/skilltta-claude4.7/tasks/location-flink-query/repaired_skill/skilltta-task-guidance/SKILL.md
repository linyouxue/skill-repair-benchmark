---
name: skilltta-task-guidance
description: Guidance for implementing the Flink LongestSessionPerJob task over Google cluster-usage traces, with corrections for stage/session detection and output eligibility.
---

# SkillTTA Task Guidance: Longest Stage Per Finished Job (Flink)

## Context
You are implementing `clusterdata.query.LongestSessionPerJob` (Flink streaming job) that:
- Reads a gzipped task_events CSV and a gzipped job_events CSV (Google cluster-usage traces, timestamps in microseconds).
- Groups task SUBMIT events (event type = 0) per `jobId` into "stages" separated by >=10 minutes of inactivity (session gap on event time).
- For each **finished** job, emits `(jobId, maxTasksInAnyStage)` to a local output file, one tuple per line.

## Data schema reminders
- task_events columns: `timestamp, missing_info, job_id, task_index, machine_id, event_type, user, scheduling_class, priority, cpu, memory, disk, different_machine`.
- job_events columns: `timestamp, missing_info, job_id, event_type, user, scheduling_class, job_name, logical_job_name`.
- Event types (both tables): 0=SUBMIT, 1=SCHEDULE, 2=EVICT, 3=FAIL, 4=FINISH, 5=KILL, 6=LOST, 7=UPDATE_PENDING, 8=UPDATE_RUNNING.
- Timestamps are microseconds since trace start. 10 minutes = `10 * 60 * 1_000_000` microseconds.

## Workflow 1 — Project wiring
1. Keep class name `LongestSessionPerJob` and extend `clusterdata.utils.AppBase` (do not edit `pom.xml`).
2. Create POJO/Tuple classes under `clusterdata.datatypes`, e.g. `TaskEvent` and `JobEvent`, with `timestamp (long µs)`, `jobId (long)`, `taskIndex (long, task only)`, `eventType (int)`, and other fields you need. Provide no-arg constructor + public fields (or getters/setters) so Flink's POJO serializer works.
3. Parse CSVs with a `GZIPInputStream` reader source or `readTextFile` + manual gunzip; emit events with an event-time `WatermarkStrategy.forBoundedOutOfOrderness(Duration.ofSeconds(0))` keyed by `timestamp` (convert µs → ms for Flink watermarks via `/1000`). Make sure to assign timestamps in microseconds consistently inside your own state logic.

## Workflow 2 — Stage detection and job-finish gating (CRITICAL)
This is where prior attempts commonly fail; follow these rules exactly.

### 2.1 What counts as a task SUBMIT in a stage
- Only task events with `event_type == 0` (SUBMIT) contribute to stage task counts.
- If a task is submitted, then FAILS/EVICTED/KILLED and later re-SUBMITTED, each SUBMIT is counted separately (do not deduplicate by `(jobId, taskIndex)`).

### 2.2 Session/stage gap rule
- Use **event time** gaps, not processing time.
- A stage ends when there is no SUBMIT for that `jobId` for **>= 10 minutes (600_000_000 µs)**.
- Implement with either:
  - Flink `EventTimeSessionWindows.withGap(Time.minutes(10))` keyed by `jobId` over the SUBMIT stream, counting elements per window, then reducing to the max per job; OR
  - A `KeyedProcessFunction` with per-key state `{currentCount, maxCount, lastSubmitTs}` and an event-time timer at `lastSubmitTs + 10min`; on timer fire, close the stage (`maxCount = max(maxCount, currentCount); currentCount = 0`).

### 2.3 Job-finish determination (broadened terminal set + end-of-input flush)
A job should be treated as **finished** when ANY of the following is true:
1. A **job_events** record for that `jobId` arrives with a terminal event type. Treat the following as terminal: `FINISH (4)`, `KILL (5)`, `FAIL (3)`, `EVICT (2)`, `LOST (6)`. In practice 3/4/5 are the dominant terminal signals; including 2/6 avoids missing edge-case completions. `SUBMIT (0)`, `SCHEDULE (1)`, `UPDATE_PENDING (7)`, `UPDATE_RUNNING (8)` are NOT terminal.
2. The input stream has been fully consumed and the watermark advances to `Long.MAX_VALUE` (`MAX_WATERMARK`). On bounded input this acts as an implicit terminal signal: any job that had SUBMIT activity but never received an explicit terminal job_event should still be flushed. This prevents dropping jobs whose completion was never recorded in the sliced input.

Do NOT infer completion solely from a 10-minute task-SUBMIT gap — the 10-minute rule only closes a *stage*, not the *job*. Use the session timer to roll `currentStageCount` into `maxStageCount`, and use the terminal job_event (or end-of-input) to decide when to emit.

Union the task-event and job-event streams keyed by `jobId`, or connect them with `connect(...).keyBy(jobId, jobId)` so a `CoProcessFunction`/`KeyedCoProcessFunction` sees both. Maintain per-job state: `maxStageCount`, `currentStageCount`, `jobFinished (boolean)`, `lastSubmitTs`, `emitted (boolean)`.

### 2.4 Output eligibility
- Emit `(jobId, maxStageCount)` once per job, when **both** of these have happened:
  1. The job has been marked finished per 2.3 (either a terminal job_event in {2,3,4,5,6} arrived, OR end-of-input/`MAX_WATERMARK` was reached), AND
  2. Any still-open stage has been folded into `maxStageCount`. If a terminal job_event arrives while a stage is still open (i.e. the 10-minute timer has not fired), flush it immediately: `maxStageCount = max(maxStageCount, currentStageCount); currentStageCount = 0`.
- Jobs with **zero SUBMIT events** must not be emitted (`maxStageCount == 0` means no stage ever existed).
- Emit **exactly one** line per finished job. Guard with an `emitted` flag (or clear per-key state after emission) to prevent duplicates when both a terminal job_event and end-of-input occur.
- Do not require any specific arrival order between the terminal job_event and the stage-closing timer; whichever happens later triggers emission.

### 2.5 End-of-stream flushing
- Register an on-timer handler keyed to `Long.MAX_VALUE` (or implement `processWatermark`/`close` logic) so that when the bounded input finishes:
  - Any open stage for every job is closed (fold `currentStageCount` into `maxStageCount`).
  - Every job that has at least one SUBMIT is emitted exactly once, regardless of whether a terminal job_event was observed.
- If running in bounded/batch mode, calling `env.execute()` after `DataStream#sinkTo` is sufficient; make sure the sink is a `FileSink` or `writeAsText(path).setParallelism(1)` so output is a single local file with one tuple per line.

## Workflow 3 — Output formatting
- Each line must be exactly `(jobId,maxStageCount)` with no spaces, e.g. `(6253031646,42)`.
- Use `Tuple2<Long, Long>` and override its `toString()` via a `MapFunction` that returns `"(" + f0 + "," + f1 + ")"` to avoid Flink's default `"(a,b)"` which already matches — but double-check no extra whitespace. Write with parallelism 1 to the `output` path argument.

## Workflow 4 — Argument parsing
- Accept `--task_input`, `--job_input`, `--output` via `ParameterTool.fromArgs(args)` and pass to your sources/sink. Overwrite the output file if it exists (`FileSink` with `OutputFileConfig` or delete beforehand).

## Transfer patterns from retrieved examples
The retrieved Python examples (CSV parsing with `pd.read_csv`/`csv.reader`, filtering by prefix, writing CSV outputs) reinforce two reusable habits applicable here:
1. **Parse strictly by column index/name and coerce types early** — do the same when splitting CSV lines in Java (`line.split(",", -1)`, then `Long.parseLong` with guards for empty fields like `machine_id`).
2. **Separate IO from logic** — keep the gunzip+CSV parsing in a dedicated source function and keep stage/finish logic in `KeyedCoProcessFunction`, mirroring how the examples isolate loading from counting.

## Self-check before finishing
- [ ] Only `event_type==0` task rows increment stage counts; repeats counted separately.
- [ ] Stage closes strictly on `>= 10 min` event-time inactivity.
- [ ] Job marked finished on job_events terminal types {2,3,4,5,6} OR on end-of-input (`MAX_WATERMARK`), not from task inactivity alone.
- [ ] On terminal job_event arrival, any still-open stage is flushed into `maxStageCount` before emission.
- [ ] Output emitted ONLY for jobs with ≥1 SUBMIT; exactly one line each; format `(jobId,count)` with no spaces.
- [ ] End-of-input watermark flushes open stages AND emits any finished-but-unemitted jobs; emission is idempotent (guarded by an `emitted` flag).
- [ ] Writes to the `--output` path as a single local text file.
