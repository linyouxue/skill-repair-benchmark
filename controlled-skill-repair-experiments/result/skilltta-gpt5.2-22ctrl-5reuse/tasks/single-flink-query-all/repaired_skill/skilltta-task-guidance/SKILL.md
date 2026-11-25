---
name: skilltta-task-guidance
---

# SkillTTA Temporary Task-Guidance: Longest Stage (Session) per Finished Job in Flink

## Goal
Build a Flink job that:
1) Parses **task-events** and **job-events** (gzipped CSV text lines).
2) For each **jobId**, identifies **stages** as *bursts* of **task SUBMIT** events separated by at least **10 minutes of inactivity** (in event time).
3) Finds, per job, the **maximum number of task SUBMIT events within any single stage**.
4) **Outputs results only for jobs that have finished** (per job-events completion semantics).
5) Writes one tuple per job as exactly: `(jobId,longestStageTaskCount)` (one line each; order unimportant).

> Counting rule: if the “same task” is submitted multiple times (fail/evict/resubmit), **count each SUBMIT separately**.

---

## Key Definitions
- **Stage**: a session of **task SUBMIT** events for a job.
- **Session gap**: **10 minutes** of no SUBMITs for that job.
- **Longest stage**: the stage with the maximum SUBMIT count for that job.
- **Job finished**: determined from **job-events** by the dataset’s completion/terminal event types (see `ClusterData2011_2.md` / `format.pdf`).
  - Workflow requirement: completion must be based on the **proper job terminal event(s)**; do not guess.
  - Common terminal events in this dataset family: `FINISH`, and often also `KILL`/`FAIL` as terminal; use the schema docs.

---

## Workflow 1 — Robust Parsing + Minimal Fields

### 1. Implement datatypes under `clusterdata.datatypes`
Create two POJOs (or simple classes) expected by `clusterdata.utils.AppBase`:
- `TaskEvent`
  - Required fields: `long timestamp`, `long jobId`, `int eventType` (optionally `long taskIndex` if needed for debug).
- `JobEvent`
  - Required fields: `long timestamp`, `long jobId`, `int eventType`.

### 2. Parse CSV safely (pattern: “load → filter → transform”)
Use a `MapFunction<String, TaskEvent>` / `JobEvent` with:
- Split by comma.
- Handle empty fields (treat as `-1` or skip line).
- Skip malformed lines (return `null` then `filter(Objects::nonNull)`).

### 3. Timestamp unit handling
Dataset timestamps are **microseconds**.
- Flink event-time APIs operate on `long` and are unit-agnostic, but built-in `Time.minutes(10)` is in **milliseconds**.
- Recommended: convert to **milliseconds** early:
  - `eventTimeMs = timestampMicros / 1000L`
  - Define session gap as `Time.minutes(10)` (i.e., 600,000 ms).

---

## Workflow 2 — Stage Detection + Completion-Gated Output (critical)

### Step A: Extract and sessionize task SUBMIT events
1) Filter task-events to **SUBMIT only** using the event-type code from docs.
2) Assign timestamps & watermarks:
- If input is mostly time-ordered, `forMonotonousTimestamps()` is OK.
- Safer for traces: `forBoundedOutOfOrderness(Duration.ofMinutes(1))`.

3) Key by `jobId` and define stages via **event-time session windows**:
- `EventTimeSessionWindows.withGap(Time.minutes(10))`

4) Count SUBMITs per session window:
- Use an `AggregateFunction` (count) or `ProcessWindowFunction`.
- Output per window: `(jobId, stageCount)`.

### Step B: Reduce to maximum stage size per job
From `(jobId, stageCount)`:
- `keyBy(jobId)`
- `reduce(maxBy stageCount)` or `max(1)`
Result stream: `(jobId, maxStageCountSoFar)`.

### Step C (Workflow requirement): Emit results **only after the job is finished**
You must gate final output using **job-events**:
1) From job-events, filter to the **job terminal/completion** event type(s) per schema docs.
2) Key completion stream by `jobId`.
3) Connect completion stream with the `maxStageCount` stream using a `KeyedCoProcessFunction`:

State to maintain per job:
- `ValueState<Integer> maxStage` (default 0)
- `ValueState<Boolean> finished` (default false)
- `ValueState<Long> finishTsMs` (optional)

Logic:
- On receiving `(jobId, maxStageCandidate)`:
  - update `maxStage = max(maxStage, candidate)`.
- On receiving a finish event for `jobId`:
  - set `finished = true`, store `finishTsMs`.
  - register an **event-time timer** at `finishTsMs + sessionGapMs`.
    - Rationale: ensures the last session window (which closes on inactivity) has had time (in event-time) to emit.
- On timer:
  - if `finished == true`, emit exactly once: `(jobId, maxStage)`.
  - optionally clear state to avoid duplicates.

> Result output qualification (per Workflow 2): only jobs with a valid terminal event should produce output; avoid emitting for jobs that never finish in the provided slice.

---

## Output Formatting & Sink
- Use `Tuple2<Long, Integer>` (or `Tuple2<Integer,Integer>` if jobId safely fits) so Flink’s default `toString()` prints exactly:
  - `(jobId,maxStageCount)`
- Write to a **single local file**:
  - `writeAsText(output, FileSystem.WriteMode.OVERWRITE).setParallelism(1)`

---

## Practical Checklist (avoid common failures)
- [ ] SUBMIT event-type codes taken from dataset docs, not assumed.
- [ ] Job completion/terminal event-type codes taken from dataset docs (FINISH, and possibly others if specified).
- [ ] Convert timestamps from microseconds → milliseconds (or keep microseconds consistently, but then the gap must match).
- [ ] Session gap is exactly 10 minutes in event time.
- [ ] Count all SUBMITs (including resubmissions).
- [ ] Emit **one line per finished jobId**.
- [ ] Set sink parallelism to 1 to avoid multiple part-files.

---

## Minimal Architecture Summary
`task_events.gz` → parse → filter SUBMIT → watermark → session window (10m gap) → count per session → max per job → connect with `job_finish` stream → timer-based finalize → write tuples
