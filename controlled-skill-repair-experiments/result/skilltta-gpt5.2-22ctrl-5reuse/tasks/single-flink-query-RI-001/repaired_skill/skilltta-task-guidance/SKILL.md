---
name: skilltta-task-guidance
---

# SkillTTA Temporary Task-Guidance: Flink “Longest Stage (Session) per Job”

This guidance describes a robust, reusable approach to implement a Flink DataStream job that:

- reads **gzipped CSV** task/job event files,
- identifies **stages** (= session windows) of **task SUBMIT** events per job,
- closes a stage after **10 minutes inactivity** (no SUBMIT for that job in event time),
- once a job is **finished**, outputs `(jobId,longestStageTaskCount)`.

The output order is irrelevant; correctness is per `jobId`.

---

## Key Definitions (translate directly into code)

1. **Stage/session** (per job): consecutive `TASK_SUBMIT` events separated by gaps **< 10 minutes**.
2. **Stage ends**: when the gap since the most recent `TASK_SUBMIT` reaches **10 minutes**.
3. **Longest stage**: maximum number of submitted tasks in any stage for that job.
4. **Job completion / finished**:
   - Use the **job event stream** to detect terminal job lifecycle.
   - Treat the job as “finished” when a **terminal job event** occurs (per the dataset spec in `ClusterData2011_2.md`). Common terminal types are typically `FINISH`, and often also `KILL`, `FAIL`, `LOST` depending on the trace definition.
   - **Important:** do not emit purely because input ends; define a **terminal-event predicate** from the spec, and emit only once the job is finished **in event time**, i.e., after the watermark has passed a safe point beyond the terminal timestamp (terminal_ts + allowed lateness / out-of-orderness bound).

---

## Workflow 1 — Parse inputs (gzipped CSV) into POJOs

### 1.1 Read `.csv.gz`
- Flink can read `.gz` transparently if you use `env.readTextFile(path)` or a `FileSource` with line-based format.
- Keep the pipeline bounded (batch-like), but still use event time.

### 1.2 Implement required datatypes (`clusterdata.datatypes`)
Implement POJO-style classes referenced by `clusterdata.utils.AppBase` (as the skeleton requires). Keep them minimal but complete:

- `TaskEvent`:
  - `long timestamp` (convert microseconds → milliseconds)
  - `long jobId`
  - `int eventType`
  - (optional) other fields you may want to parse safely

- `JobEvent`:
  - `long timestamp` (micro → milli)
  - `long jobId`
  - `int eventType`

Parsing tips (CSV robustness pattern):
- Split with `line.split(",", -1)`.
- Guard against malformed/empty lines.
- Only parse the columns you need; ignore others.

### 1.3 Normalize timestamps
Dataset timestamps are **microseconds**.
- Convert: `eventTimeMs = timestampMicros / 1000L`.
- Compute inactivity gap: `GAP_MS = 10 * 60 * 1000L`.

---

## Workflow 2 — Build a unified event stream keyed by jobId

### 2.1 Create a tagged union type
Create a small internal type (e.g., `UnifiedEvent`) containing:
- `long jobId`
- `long tsMs`
- `Kind kind` where `Kind ∈ {TASK_SUBMIT, JOB_TERMINAL, OTHER}`

Map:
- From `TaskEvent` → `UnifiedEvent(TASK_SUBMIT)` **only** when the task event is `SUBMIT`.
- From `JobEvent` → `UnifiedEvent(JOB_TERMINAL)` **only** when the job event is terminal (FINISH/KILL/FAIL/etc. per spec).

Union the two streams and `keyBy(jobId)`.

### 2.2 Event-time and watermarks
Assign timestamps and watermarks on the unified stream.
- Use `WatermarkStrategy.forBoundedOutOfOrderness(Duration.ofMinutes(X))`.
- Pick `X` conservatively (e.g., 1–5 minutes) unless the dataset docs indicate strict ordering.

This enables:
- correct session closing via event-time timers,
- safe “emit-after-finish” via a finish-time timer.

---

## Workflow 3 — Sessionize SUBMITs with keyed state + timers

Implement a `KeyedProcessFunction<Long, UnifiedEvent, Tuple2<Long,Integer>>`.

### 3.1 State you need (per job)
- `ValueState<Integer> currentStageCount`
- `ValueState<Integer> maxStageCount`
- `ValueState<Long> lastSubmitTsMs`
- `ValueState<Long> expectedInactivityTimerTsMs`
- `ValueState<Long> terminalJobTsMs` (nullable)
- `ValueState<Long> expectedEmitTimerTsMs` (nullable)
- `ValueState<Boolean> hasQualifyingActivity` (for the Non-negotiable Flink Emission Gate)

### 3.2 On TASK_SUBMIT
1. Increment `currentStageCount`.
2. Set `hasQualifyingActivity = true` (eligibility is created only by contributing activity).
3. Set `lastSubmitTsMs = event.tsMs`.
4. Schedule/refresh inactivity timer at `event.tsMs + GAP_MS`:
   - store `expectedInactivityTimerTsMs = inactivityTs`;
   - `ctx.timerService().registerEventTimeTimer(inactivityTs)`.

Because Flink can’t “cancel” event-time timers directly, always **verify** the timer timestamp in `onTimer` using `expectedInactivityTimerTsMs`.

### 3.3 On inactivity timer (`onTimer`)
If `timestamp == expectedInactivityTimerTsMs`:
- stage ended → update max:
  - `maxStageCount = max(maxStageCount, currentStageCount)`
- reset stage:
  - `currentStageCount = 0`
  - `lastSubmitTsMs = null`
  - `expectedInactivityTimerTsMs = null`

### 3.4 On JOB_TERMINAL (job finished detection)
Follow the completion rule hinted in the task:

1. Record terminal time:
   - `terminalJobTsMs = min(existingTerminal, event.tsMs)` (first terminal wins)
2. Do **not** emit immediately; instead schedule an emit timer:
   - `emitTs = terminalJobTsMs + outOfOrderAllowanceMs + 1`
   - store `expectedEmitTimerTsMs = emitTs`
   - register event-time timer at `emitTs`

This ensures you include any late-arriving SUBMIT events that are still within watermark tolerance.

### 3.5 On emit timer
If `timestamp == expectedEmitTimerTsMs`:
- finalize any open stage:
  - `maxStageCount = max(maxStageCount, currentStageCount)`
- emit **only if eligible** (Non-negotiable Flink Emission Gate):
  - if `hasQualifyingActivity != true`, do not emit a row
  - if `maxStageCount` is null, do not emit a row
  - else output `Tuple2.of(jobId, maxStageCount)`
- clear all states (job done).

---

## Workflow 4 — Format and write output exactly

Required line format per record:
- `(first_int,second_int)`

Implementation pattern:
- Map `Tuple2<Long,Integer>` → `"(" + f0 + "," + f1 + ")"`.
- Use a sink that writes one line per tuple.

To avoid multi-part outputs in tests, prefer:
- `env.setParallelism(1)` **or** `sink.setParallelism(1)`.
- `writeAsText(outputPath, FileSystem.WriteMode.OVERWRITE)`.

---

## Validation & Edge Cases Checklist (apply before final submission)

- **Terminal events:** confirm which `job_event.event_type` values are terminal using `ClusterData2011_2.md`.
- **Only count SUBMIT:** ignore other task event types.
- **Resubmits counted separately:** do not deduplicate `(job, taskIndex)`.
- **No-activity keys:** by default, do **not** emit a row for a job that has lifecycle/terminal events but no qualifying SUBMIT activity, unless the task explicitly requires zero-valued outputs.
- **Timer correctness:** ignore stale timers by checking `expected*TimerTs`.
- **Timestamp units:** ensure everything is consistently in milliseconds after parsing.

---

## Minimal mental model (portability)

Think of each jobId as a mini “Counter with session breaks”:
- SUBMIT increments the current counter and pushes an inactivity deadline.
- When the deadline passes, seal the session and update the max.
- When a terminal job event occurs, schedule a watermark-safe finalization time and then (if eligible) emit the max.
