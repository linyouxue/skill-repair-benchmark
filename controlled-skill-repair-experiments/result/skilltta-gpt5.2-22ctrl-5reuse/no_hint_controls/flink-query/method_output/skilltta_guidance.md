# SKILL.md

## When to use
Use this skill when you must implement a Java Apache Flink batch/stream job from a provided skeleton to compute **per-entity sessionized/staged aggregates** from event logs, where:
- “Stages/sessions” are defined by **event-time gaps** (e.g., inactivity gap threshold) within a key (e.g., per job).
- Input is **gzipped CSV** with a schema described in accompanying docs.
- Output must be written to a **local file** in a **strict line format** and will be evaluated by comparing computed values (ordering not important).

Before coding, gather evidence from:
- The dataset schema documentation (field order, types, meaning of event types).
- The skeleton’s `AppBase` expectations (what datatype classes must exist, how parsing is wired, what parameters are passed).
- Time semantics: timestamp unit (e.g., **microseconds**) and required gap duration (e.g., **10 minutes**) in the same unit.

## Possible Failure Modes
- **Wrong time unit conversion**: treating microseconds as milliseconds/seconds causes incorrect session gaps and stage boundaries.
- **Using processing time instead of event time**: sessionization based on arrival time rather than event timestamp breaks correctness.
- **Incorrect stage definition**: using fixed windows/tumbling windows instead of session windows (gap-based), or ending stages on the wrong event type.
- **Counting the wrong events**: including non-`SUBMIT` events, filtering incorrectly, or joining/reading the wrong stream as the event source.
- **Incorrect counting semantics**: deduplicating tasks when the contract requires counting resubmissions separately, or counting unique task IDs instead of counting `SUBMIT` occurrences.
- **Not ensuring “job finished” constraint**: outputting partial results for jobs that have not ended, or not properly using job events to filter to finished jobs when required by the contract.
- **Parser/schema mismatch**: wrong CSV column indices, incorrect numeric parsing, not handling missing values, or failing on header/no-header assumptions.
- **Gzip input handling issues**: using an input format that doesn’t support `.gz` or misconfiguring Flink file source.
- **Output format mismatch**: not exactly `(first_int,second_int)` per line, extra spaces, additional fields, or writing to the wrong path.
- **Compilation failures due to missing required datatypes**: skeleton references datatype classes; leaving them unimplemented breaks build.
- **Keying/partitioning mistakes**: forgetting to key by job ID before sessionization, causing cross-job mixing.

## Possible procedures
1. **Read and map schemas**
   - From the provided schema docs, identify:
     - Event timestamp field and its unit.
     - Fields needed to filter `SUBMIT` task events.
     - Job lifecycle fields needed to determine “job finished” (if the job-event stream is required).
   - Cross-check these with any parsing utilities in the skeleton/AppBase.

2. **Implement required datatype classes (for compilation + parsing)**
   - Create Java POJOs (or Flink-serializable types) for task events and job events matching the skeleton’s expected package/class names.
   - Include only fields needed for logic + any fields AppBase parser requires.
   - Add robust parsing helpers:
     - Safe numeric parsing (guard empty strings).
     - Keep raw timestamp as `long` and only convert when necessary.

3. **Build the task-event pipeline (stage identification)**
   - Source: read the gzipped CSV task-event file via the skeleton’s prescribed method.
   - Filter to relevant events (e.g., only `SUBMIT`).
   - Extract a stream of `(jobId, eventTime)` (and optionally `1` as a count-per-submit).
   - Assign **event-time timestamps** and a watermark strategy appropriate for bounded data (often “monotonous” or “bounded out-of-orderness” depending on evidence from the dataset and docs).

4. **Sessionize into stages**
   - Key by `jobId`.
   - Use a **session window** with the contract’s inactivity gap (convert 10 minutes into the dataset’s timestamp unit).
   - Aggregate within each session to compute **number of submits** (or “tasks”) in that stage:
     - Prefer incremental aggregation (e.g., `AggregateFunction`) to avoid buffering.
     - Ensure each submit counts as 1 even if task identifiers repeat across time (no dedup).

5. **Select the longest stage per job**
   - After computing per-(jobId, session) counts, reduce per job to the **maximum** stage count.
   - If you must ensure “once the job has finished,” incorporate job events:
     - Identify a reliable job-finished signal from job events.
     - Join/filter so only finished jobs produce output (e.g., broadcast finished-job IDs, or join on jobId in bounded mode).
   - Keep the pipeline bounded and produce exactly one output record per job.

6. **Write results with strict formatting**
   - Map results to strings exactly like `(jobId,longestStageTaskCount)`.
   - Write one tuple per line to the specified output path using Flink’s file sink compatible with the runtime (as implied by the skeleton).
   - Do not add headers or extra logging into the output file.

7. **Recovery checks / debugging approach**
   - If results look empty: confirm filters (event type constants), schema indices, and timestamp assignment.
   - If results are wildly off: re-check timestamp unit conversion and session gap computation.
   - If compilation fails: confirm package names, class names, and field accessibility match skeleton expectations.

## Verification Checklist
- [ ] Datatype classes required by the skeleton exist under the expected packages and compile successfully.
- [ ] Task events are filtered to the correct event type(s) used to define stages (e.g., only `SUBMIT`).
- [ ] Event time is used (not processing time), and timestamps are interpreted in the dataset’s stated unit (e.g., microseconds).
- [ ] Session/stage gap equals **10 minutes** expressed in the correct unit; session windows are used (not tumbling/sliding windows).
- [ ] Stage “task count” equals the number of submit occurrences in that stage; resubmissions are counted separately (no unintended dedup).
- [ ] Exactly one final record per job is produced: `(jobId, maxStageTaskCount)`; line order is not relied upon.
- [ ] Output file path is the one passed via parameters; output has one tuple per line with exact parentheses/comma formatting and no extra fields.
- [ ] No unrelated project files (e.g., build config/class name) were modified against constraints.
- [ ] If job-finished filtering is required by the contract, validate that unfinished jobs do not emit output (spot-check with small samples).
- [ ] Re-run after any parsing/schema changes to ensure no silent parse failures (e.g., counters/logging during development, removed/disabled before final).
