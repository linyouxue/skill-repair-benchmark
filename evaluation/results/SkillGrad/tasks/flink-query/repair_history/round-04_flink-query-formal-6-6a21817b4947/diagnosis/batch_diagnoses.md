# Batch Diagnoses

## Task flink-query (reward: 0.0)

<label>Stateful session logic wrong</label>

(1) **First observable failure**
- The job produced **incorrect counts** for “number of tasks in the longest stage per job” (grader reward 0 with successful execution indicates logical mismatch, not compile/runtime failure).

(2) **Trajectory step that produced it**
- The **implementation step of the Flink pipeline** in `LongestSessionPerJob` where stages were inferred and aggregated. The first failing behavior is the **stage boundary / counting semantics**: the code likely did not implement “SUBMIT-event sessions separated by 10 minutes inactivity in *event time* per job” exactly, or it mixed job-termination logic incorrectly.

(3) **Relevant skill rule or missing rule**
- Missing/violated rule in the data-engineer/Flink procedure:  
  **“Use event-time sessionization keyed by entity with an inactivity gap, and count events within each session; then take per-key max over sessions, emitting at end-of-input.”**  
  Common omission: not using **event time watermarks** (microseconds), using processing time, or not doing a **two-level aggregation** (session count → max-per-job). Another frequent miss is counting distinct taskIds rather than counting submit events (the prompt requires counting resubmits separately).

(4) **General corrective behavior**
- Implement stages as **event-time sessions per jobId** over **task SUBMIT events only** with a **10-minute gap**, ensuring timestamps are converted from microseconds and watermarks are assigned.
- Compute: `keyBy(jobId) -> window(EventTimeSessionWindows.withGap(10min)) -> aggregate count of SUBMIT records -> then keyBy(jobId) -> max(count)` and write `(jobId,longestStageTaskCount)`.
- Ensure counting is **per SUBMIT record** (not dedup by taskId), and that output is produced deterministically at end-of-bounded input (final watermarks / bounded source semantics), without relying on job events unless explicitly required for correctness.

Error type: **skill-controllable logic error** (not an API/permission/harness issue; execution was OK).

Evidence:
- trace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/flink-query/iter_5/trace.jsonl
- assessment: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/flink-query/iter_5/assessment.json
- workspace: /home/linyuanjing/SkillGrad/experiments/skillgrad_skillsbench87_31/batch/flink-query/workspace
