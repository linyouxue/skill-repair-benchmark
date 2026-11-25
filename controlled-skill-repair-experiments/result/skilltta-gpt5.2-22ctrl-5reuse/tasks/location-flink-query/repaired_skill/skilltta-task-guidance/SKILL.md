---
name: skilltta-task-guidance
---

# SkillTTA Task Guidance: Flink “Longest Session/Stage per Job” (Google Cluster Traces)

This skill provides a reusable workflow for implementing a Flink job that:
1) parses gzipped CSV event logs,
2) groups events by `jobId`,
3) performs **sessionization** (a.k.a. stage detection) on **SUBMIT** task events with a fixed inactivity gap (10 minutes),
4) emits results **only when a job has finished** (per job-event terminal states),
5) writes output as one tuple per job: `(jobId,longestStageTaskCount)`.

It is designed for Google cluster-usage traces style schemas (timestamps in microseconds) and typical Flink streaming/bounded execution.

---

## 1) Data handling patterns (gz CSV → typed events)

### 1.1 Read gzipped CSV
- Prefer Flink’s file sources that transparently handle `.gz` (common in local/HDFS setups).
- If the project skeleton uses `env.readTextFile(path)`, keep it unless proven unsupported.
- Parsing is usually: `DataStream<String>` → `map(parseCsvLine)` → `filter(valid)`.

### 1.2 Robust CSV parsing
Google trace lines can include empty fields.
- Split with `line.split(",", -1)` to preserve trailing empties.
- Provide helpers:
  - `parseLong(field, defaultValue)`
  - `parseInt(field, defaultValue)`
- Drop header lines if present (many parts don’t have headers, but be defensive).

### 1.3 Time unit normalization (microseconds)
Flink event-time APIs (watermarks, timers) are easiest to use in **milliseconds**.
- Convert on ingest:
  - `eventTimeMs = timestampMicros / 1000L`
- Then the 10-minute inactivity gap is:
  - `GAP_MS = 10 * 60 * 1000L`

---

## 2) Define minimal POJOs under `clusterdata.datatypes`

Implement the event classes referenced by the base app (as required by the task):

### 2.1 TaskEvent (minimum fields)
Include at least:
- `long timestampMs`
- `long jobId`
- `int eventType`
- (optional) `long taskIndex` / `int priority` etc. if needed for debugging

Provide a predicate:
- `isSubmit()` → true iff task `eventType` equals the dataset’s SUBMIT code.

### 2.2 JobEvent (minimum fields)
Include at least:
- `long timestampMs`
- `long jobId`
- `int eventType`

Provide a predicate:
- `isTerminal()` → true for job completion states.
  - Use the dataset docs (`format.pdf`, `ClusterData2011_2.md`) to identify which codes are terminal.
  - Common Google traces mapping (verify in docs):
    - `FINISH`, `KILL`, `FAIL`, `LOST` are terminal.

---

## 3) Stage/session definition and counting

### 3.1 Stage definition
For a given `jobId`:
- Consider **only task SUBMIT events**.
- A **stage** is a run of SUBMIT events with inter-arrival gaps ≤ 10 minutes.
- A stage ends when there is an **inactivity period** of 10 minutes with no SUBMIT for that job.
- If the same task is resubmitted later, count it again (count SUBMIT events, not unique task ids).

### 3.2 What to output
For each job that *finishes*:
- Output `(jobId, longestStageTaskCount)`
- “longest” here means **largest number of SUBMIT events within a stage**.

---

## 4) Stateful Flink design (recommended)

### 4.1 Keyed connected streams (tasks + job events)
You typically need both:
- Task SUBMIT stream (to build stages)
- Job terminal stream (to know when to emit)

Pattern:
1) Parse `task_events` → filter SUBMIT → key by `jobId`
2) Parse `job_events` → filter terminal → key by `jobId`
3) `connect()` the two keyed streams
4) Process with `KeyedCoProcessFunction<Long, TaskEvent, JobEvent, Tuple2<Long,Integer>>`

This allows:
- updating counts on SUBMITs
- emitting final result immediately upon job terminal event

### 4.2 Per-job state you need
Use Flink keyed state:
- `ValueState<Integer> currentStageCount`
- `ValueState<Integer> maxStageCount`
- `ValueState<Long> lastSubmitTsMs`
- `ValueState<Long> inactivityTimerTsMs` (timestamp of currently-registered stage-end timer)
- `ValueState<Boolean> jobFinished` (or store terminal event ts)

### 4.3 Session boundary logic (SUBMIT side)
On each SUBMIT at time `t`:
1) If `lastSubmitTs` is null → new stage.
2) Else if `(t - lastSubmitTs) > GAP_MS`:
   - close prior stage: `max = max(max, currentStageCount)`
   - start new stage: `currentStageCount = 0`
3) Increment: `currentStageCount++`
4) Update `lastSubmitTs = t`
5) (Re)register inactivity timer for `t + GAP_MS`:
   - if an old timer exists, `deleteEventTimeTimer(old)`
   - `registerEventTimeTimer(t + GAP_MS)`
   - store new timer timestamp in state

### 4.4 Timer callback (stage ends due to inactivity)
On `onTimer(timerTs)`:
- This timer represents “no SUBMIT for GAP_MS”.
- Update `max = max(max, currentStageCount)`
- Reset `currentStageCount = 0`
- Reset `lastSubmitTs = null`
- Clear `inactivityTimerTs`

Do **not** emit here unless the job is known finished (you can, but it’s safer to emit only on job terminal to match “once the job has finished”).

### 4.5 Job terminal event handling (emit eligibility)
On terminal job event:
1) Mark job as finished.
2) Before emitting, ensure you account for the current open stage:
   - `max = max(max, currentStageCount)`
3) Emit `(jobId, max)`.
4) Clear all state for this key.

**Emit eligibility rule:** output only for jobs for which a terminal job event is observed in the input (per dataset terminal types).

---

## 5) Event-time + watermarks (bounded files)

For file/batch-like inputs, use a watermark strategy that:
- assigns timestamps from `timestampMs`
- uses monotonous timestamps if the file is sorted, or bounded out-of-orderness if not.

Recommended defaults:
- If traces are approximately sorted: `WatermarkStrategy.forMonotonousTimestamps()`
- Otherwise: `forBoundedOutOfOrderness(Duration.ofSeconds(X))`

Important: the watermark delay must be in the same unit as your timestamps (hence converting to ms).

---

## 6) Output formatting and sink

### 6.1 Exact formatting
Convert result tuples to strings:
- `"(" + jobId + "," + longest + ")"`

### 6.2 Write to local file
Use a sink compatible with the execution mode provided by the skeleton.
Common options:
- `DataStream<String>.writeAsText(outputPath).setParallelism(1)`
- or FileSink/StreamingFileSink if required

Order is not required; one line per tuple is required.

---

## 7) Quick checklist for correctness

- [ ] Timestamps are converted from microseconds → milliseconds consistently.
- [ ] Only **task SUBMIT** events affect stage counts.
- [ ] Gap logic uses strict `>` (inactivity strictly longer than 10 minutes ends stage).
- [ ] Resubmissions are counted (count SUBMIT events, not unique tasks).
- [ ] Terminal job event types match the dataset docs.
- [ ] Output emitted only when job is finished.
- [ ] State is cleared after emitting to avoid leaks.

---

## 8) Minimal pseudocode (drop-in blueprint)

```java
// taskSubmits: parsed TaskEvent stream filtered to SUBMIT
// jobTerminal: parsed JobEvent stream filtered to terminal

KeyedStream<TaskEvent, Long> taskK = taskSubmits.keyBy(TaskEvent::getJobId);
KeyedStream<JobEvent, Long> jobK = jobTerminal.keyBy(JobEvent::getJobId);

DataStream<Tuple2<Long,Integer>> out = taskK
  .connect(jobK)
  .process(new KeyedCoProcessFunction<Long, TaskEvent, JobEvent, Tuple2<Long,Integer>>() {

    ValueState<Integer> cur;
    ValueState<Integer> max;
    ValueState<Long> last;
    ValueState<Long> timer;

    public void processElement1(TaskEvent e, Context ctx, Collector<Tuple2<Long,Integer>> out) {
      long t = e.timestampMs;
      Integer curV = cur.value(); if (curV == null) curV = 0;
      Integer maxV = max.value(); if (maxV == null) maxV = 0;
      Long lastV = last.value();

      if (lastV != null && (t - lastV) > GAP_MS) {
        maxV = Math.max(maxV, curV);
        curV = 0;
      }
      curV += 1;

      // update state
      cur.update(curV);
      max.update(maxV);
      last.update(t);

      // reset inactivity timer
      Long oldTimer = timer.value();
      if (oldTimer != null) ctx.timerService().deleteEventTimeTimer(oldTimer);
      long newTimer = t + GAP_MS;
      ctx.timerService().registerEventTimeTimer(newTimer);
      timer.update(newTimer);
    }

    public void onTimer(long ts, OnTimerContext ctx, Collector<Tuple2<Long,Integer>> out) {
      Integer curV = cur.value(); if (curV == null) curV = 0;
      Integer maxV = max.value(); if (maxV == null) maxV = 0;
      maxV = Math.max(maxV, curV);

      max.update(maxV);
      cur.update(0);
      last.clear();
      timer.clear();
    }

    public void processElement2(JobEvent e, Context ctx, Collector<Tuple2<Long,Integer>> out) {
      Integer curV = cur.value(); if (curV == null) curV = 0;
      Integer maxV = max.value(); if (maxV == null) maxV = 0;
      maxV = Math.max(maxV, curV);

      out.collect(Tuple2.of(ctx.getCurrentKey(), maxV));

      // clear all
      cur.clear();
      max.clear();
      last.clear();
      Long oldTimer = timer.value();
      if (oldTimer != null) ctx.timerService().deleteEventTimeTimer(oldTimer);
      timer.clear();
    }
  });
```

Use this blueprint to implement the actual job class logic and required datatypes in the project.
