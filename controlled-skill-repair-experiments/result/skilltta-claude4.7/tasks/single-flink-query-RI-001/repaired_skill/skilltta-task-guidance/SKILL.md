---
name: skilltta-task-guidance
description: Temporary guidance for implementing the LongestSessionPerJob Flink job over Google cluster-usage traces
---

# Task Guidance: Longest Stage per Finished Job

## Problem Restatement
Implement `clusterdata.query.LongestSessionPerJob` (Flink DataStream job) that:
1. Reads a gzipped task-events CSV and a gzipped job-events CSV.
2. Groups task SUBMIT events per `jobId` into "stages" separated by ≥10 min of SUBMIT-event-time inactivity.
3. Emits, **only for jobs that have FINISHED**, a tuple `(jobId, maxTaskCountAcrossStages)` to a local output file (one tuple per line).

## Critical Correctness Rules (read before coding)

### R1. Event-type filtering
- Google trace event types are integers. In **task_events**:
  - `SUBMIT = 0` — the ONLY event used for stage construction.
  - Resubmissions after FAIL/EVICT appear as new SUBMIT rows and MUST be counted separately (do not dedupe on taskIndex).
- In **job_events** the distinct terminal states are `FAIL = 3`, `FINISH = 4`, `KILL = 5`, `LOST = 6`. These are NOT interchangeable:
  - `FINISH (4)` means the job completed successfully — it is the only state that matches the English word "finished".
  - `KILL (5)`, `FAIL (3)`, `LOST (6)` are terminal but represent abnormal termination, not finishing.
- The task says *"once the job has finished"*. Apply the Semantic Contract Gate completion-event derivation rule: lifecycle-specific vocabulary ("finished", "completed", "succeeded") maps to the single matching lifecycle code. **The completion predicate is `job_events.event_type == 4` (FINISH) ONLY.** Do NOT broaden to {3,4,5,6}; doing so injects jobIds that the task does not request and will mismatch per-jobId comparison.
- Jobs whose only terminal lifecycle event is KILL/FAIL/LOST must NOT appear in the output, even if they have qualifying SUBMIT activity.

### R2. Time semantics
- Timestamps are **microseconds**. Convert to milliseconds for Flink watermarks (`ts / 1000`).
- The 10-minute gap is on **event time of SUBMIT events**, not wall clock. 10 min = `600_000_000` µs (or `600_000` ms once converted).
- Use `WatermarkStrategy.forBoundedOutOfOrderness(Duration.ofMinutes(1))` with the SUBMIT timestamp as the event-time extractor.

### R3. Session windowing
- Per `jobId`, use `.keyBy(jobId).window(EventTimeSessionWindows.withGap(Time.minutes(10)))` on the filtered SUBMIT stream.
- Window `ProcessWindowFunction` counts rows → emits `(jobId, stageCount, windowEnd)`.

### R4. Join with job completion (FINISH only)
- Keep a keyed state per `jobId` of the running max stage size (updated as session windows fire).
- Connect this stream with the job-events stream filtered to **FINISH (event_type == 4) only**. When a FINISH event arrives, read the current max from state and emit `(jobId, max)` — but ONLY if qualifying SUBMIT activity has been observed (see the Non-negotiable Flink Emission Gate in the senior-data-engineer skill).
- If windows arrive **after** the FINISH event, flush on each update too and dedupe downstream, OR buffer the FINISH event in state until watermark passes and session windows have fired.
- Simpler, acceptable alternative: in a `KeyedCoProcessFunction`, emit on FINISH-event arrival using whatever max is in state at that moment (acceptable because the FINISH event's timestamp is ≥ last SUBMIT).
- Receiving a FINISH event for a jobId with no SUBMIT activity must NOT synthesize a zero-count row.

### R5. Output sink
- Use `StreamingFileSink` or (simpler for a single file) collect to a `List` via `DataStream.executeAndCollect()` then write with `java.nio.file.Files.write(...)` — or use `writeAsText(output).setParallelism(1)` (deprecated but works) to produce one file.
- Format each line exactly as `(jobId,count)` — no spaces, matching the specified `(first_int,second_int)` tuple format.

## Required New Classes

Under `clusterdata.datatypes/`:
- `TaskEvent` — fields: `long timestamp; long jobId; long taskIndex; int eventType; ...` + static `fromCsv(String line)` parser.
- `JobEvent` — fields: `long timestamp; long jobId; int eventType; ...` + `fromCsv`.

CSV schemas (from `format.pdf` / `ClusterData2011_2.md`):
- task_events columns: `timestamp, missing_info, job_id, task_index, machine_id, event_type, user, scheduling_class, priority, cpu_req, mem_req, disk_req, machine_constraint`.
- job_events columns: `timestamp, missing_info, job_id, event_type, user, scheduling_class, job_name, logical_job_name`.

## Reading Gzipped CSV in Flink
```java
TextInputFormat fmt = new TextInputFormat(new Path(path));
fmt.setFilesFilter(FilePathFilter.createDefaultFilter());
DataStream<String> lines = env.readFile(fmt, path, FileProcessingMode.PROCESS_ONCE, -1);
```
Flink auto-decompresses `.gz` via `InflaterInputStreamFactory` for `TextInputFormat`. Do NOT manually `GZIPInputStream`.

## Skeleton Outline
```java
public class LongestSessionPerJob extends AppBase {
  public static void main(String[] args) throws Exception {
    ParameterTool p = ParameterTool.fromArgs(args);
    String taskInput = p.getRequired("task_input");
    String jobInput  = p.getRequired("job_input");
    String output    = p.getRequired("output");

    StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
    env.setParallelism(1); // single output file & deterministic ordering of state updates

    DataStream<TaskEvent> submits = env.readTextFile(taskInput)
        .map(TaskEvent::fromCsv).filter(e -> e.eventType == 0)
        .assignTimestampsAndWatermarks(
            WatermarkStrategy.<TaskEvent>forBoundedOutOfOrderness(Duration.ofMinutes(1))
                .withTimestampAssigner((e, ts) -> e.timestamp / 1000));

    DataStream<Tuple2<Long,Integer>> stageCounts = submits
        .keyBy(e -> e.jobId)
        .window(EventTimeSessionWindows.withGap(Time.minutes(10)))
        .process(new CountStage());

    // FINISH-only filter: event_type == 4. KILL(5)/FAIL(3)/LOST(6) are NOT "finished".
    DataStream<JobEvent> finishes = env.readTextFile(jobInput)
        .map(JobEvent::fromCsv)
        .filter(e -> e.eventType == 4)
        .assignTimestampsAndWatermarks(
            WatermarkStrategy.<JobEvent>forBoundedOutOfOrderness(Duration.ofMinutes(1))
                .withTimestampAssigner((e,ts)-> e.timestamp/1000));

    stageCounts.keyBy(t -> t.f0)
        .connect(finishes.keyBy(e -> e.jobId))
        .process(new EmitOnFinish())   // keeps running max; emits on FINISH + flush at endOfInput
        .map(t -> "("+t.f0+","+t.f1+")")
        .writeAsText(output, FileSystem.WriteMode.OVERWRITE).setParallelism(1);

    env.execute("LongestSessionPerJob");
  }
}
```

## `EmitOnFinish` details
- Keyed state `ValueState<Integer> maxStage`, `ValueState<Boolean> finished`, `ValueState<Boolean> hasQualifyingActivity`, `ValueState<Integer> emittedMax`.
- On stage-count element: update `maxStage`, set `hasQualifyingActivity = true`. If `finished==true` AND `hasQualifyingActivity==true`, re-emit if max changed.
- On FINISH event: set `finished=true`; emit current max **only if `hasQualifyingActivity==true`**. A FINISH for a job with no SUBMIT activity must NOT produce a row (do not synthesize a zero).
- Override `close()` / use a long timer at `Long.MAX_VALUE` to flush any pending finished-but-not-yet-maxed jobs, guarded by the same `hasQualifyingActivity` gate.
- This mirrors the Non-negotiable Flink Emission Gate in the senior-data-engineer skill.

## Patterns Transferred From Prior Examples
These CSV-processing patterns from unrelated prior tasks still apply conceptually:
- **Robust CSV parsing** (BigCodeBench/68, /844, /721): split with care, trim whitespace, validate column count before indexing. Apply in `TaskEvent.fromCsv` / `JobEvent.fromCsv` — skip malformed lines rather than throwing.
- **Counting + top-K selection** (BigCodeBench/721 `Counter.most_common(1)`): mirrors "max stage size per job" — maintain an incremental max rather than materialising all stages.
- **Prefix / value filtering before aggregation** (BigCodeBench/68): filter `eventType==0` *before* keying/windowing to avoid wasted shuffle, exactly as you'd filter `Employee ID` prefix before histogram.

## Build / Run Checks
- Do NOT edit `pom.xml` or rename `LongestSessionPerJob`.
- Verify the job-events filter uses **FINISH (event_type == 4) only**, not the broadened terminal set.
- Verify µs → ms conversion is applied once, consistently, to both streams.
- Verify output tuple format `(id,count)` with no spaces and `setParallelism(1)` on the sink.

## Self-Review Checklist Before Returning
- [ ] SUBMIT-only filter (event_type == 0) on task stream.
- [ ] 10-min **event-time** session gap.
- [ ] Max stage size per job maintained in keyed state.
- [ ] Emission gated on **FINISH job event (event_type == 4) only**. KILL(5)/FAIL(3)/LOST(6) do NOT trigger emission.
- [ ] A job whose only lifecycle event is KILL/FAIL/LOST must NOT appear in output.
- [ ] A job with FINISH but no SUBMIT activity must NOT appear in output (no synthesized zero rows).
- [ ] Resubmissions counted (no dedupe on taskIndex).
- [ ] Single output file, exact tuple format.
- [ ] `.gz` handled by Flink's TextInputFormat automatically.
