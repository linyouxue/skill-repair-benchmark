---

# === CORE IDENTITY ===
name: senior-data-engineer
title: Senior Data Engineer Skill Package
description: World-class data engineering skill for building scalable data pipelines, ETL/ELT systems, real-time streaming, and data infrastructure. Expertise in Python, SQL, Spark, Airflow, dbt, Kafka, Flink, Kinesis, and modern data stack. Includes data modeling, pipeline orchestration, data quality, streaming quality monitoring, and DataOps. Use when designing data architectures, building batch or streaming data pipelines, optimizing data workflows, or implementing data governance.
domain: engineering
subdomain: data-engineering

# === WEBSITE DISPLAY ===
difficulty: advanced
time-saved: "TODO: Quantify time savings"
frequency: "TODO: Estimate usage frequency"
use-cases:
  - Designing data pipelines for ETL/ELT processes
  - Building data warehouses and data lakes
  - Implementing data quality and governance frameworks
  - Creating analytics dashboards and reporting
  - Building real-time streaming pipelines with Kafka and Flink
  - Implementing exactly-once streaming semantics
  - Monitoring streaming quality (consumer lag, data freshness, schema drift)
  - Implementing Flink Java DataStream jobs with session/tumbling windows

# === RELATIONSHIPS ===
related-agents: []
related-skills: []
related-commands: []
orchestrated-by: []

# === TECHNICAL ===
dependencies:
  scripts: []
  references: []
  assets: []
compatibility: "Python 3.8+; platforms: macos, linux, windows"
tech-stack:
  - Python
  - SQL
  - Apache Spark
  - Airflow
  - dbt
  - Apache Kafka
  - Apache Flink
  - AWS Kinesis
  - Spark Structured Streaming
  - Kafka Streams
  - PostgreSQL
  - BigQuery
  - Snowflake
  - Docker
  - Schema Registry

# === EXAMPLES ===
examples:
  -
    title: Example Usage
    input: "TODO: Add example input for senior-data-engineer"
    output: "TODO: Add expected output"

# === ANALYTICS ===
stats:
  downloads: 0
  stars: 0
  rating: 0.0
  reviews: 0

# === VERSIONING ===
version: v2.1.0
author: Claude Skills Team
contributors: []
created: 2025-10-20
updated: 2025-12-16
license: MIT

# === DISCOVERABILITY ===
tags: [architecture, data, design, engineer, engineering, senior, streaming, kafka, flink, real-time]
featured: false
verified: true
---
# Senior Data Engineer

## Core Capabilities

- **Batch Pipeline Orchestration** - Airflow-based ETL/ELT pipelines with retries, dependency resolution, and monitoring.
- **Real-Time Streaming** - Kafka / Flink / Kinesis / Spark Structured Streaming pipelines with exactly-once semantics.
- **Flink Java DataStream Jobs** - Session/tumbling/sliding windows, keyed state, event-time processing, custom sources/sinks over compressed CSV.
- **Data Quality Management** - Multi-dimensional validation with independent cross-checks.
- **Performance Optimization** - Query, Spark, and pipeline tuning.

## CRITICAL: Flink Query Implementation Checklist

When implementing a Flink job that will be graded by comparing its output against a reference (common in benchmark tasks like Google cluster-trace queries), follow this checklist BEFORE reporting completion. Skipping any step has historically produced wrong-but-plausible output.

### Step 1 — Extract every semantic constant from the task text

For each numeric or categorical parameter, write down:

| Question | Where to look |
|---|---|
| Timestamp unit in the raw data? (s / ms / µs / ns) | Task text + `format.pdf` schema |
| Timestamp unit Flink expects for watermarks/session gaps? | Flink API: **milliseconds** |
| Which event-type integers count as "submit" / "finish" / "fail" / "kill" / "evict" / "schedule" / "lost"? | `format.pdf` event-type enum table |
| Which of those count as *terminal* for "job has finished"? | Task text — read the exact wording; usually FINISH only, sometimes FINISH+FAIL+KILL |
| Gap boundary: is the session split when gap `> T` or `>= T`? | Task text — "inactivity period of 10 minutes" is normally strict `>` (i.e., two events exactly T apart stay in the same session) |
| Does a resubmit / evict-then-submit count as one or two SUBMITs? | Task text — usually two |
| Should jobs with no terminal event be emitted? | Task text — usually **no** |
| Are duplicate `(job_id, task_index, event_time)` rows kept or deduplicated? | Task text — usually kept |
| Output format exactly? | Task text — `(a,b)` with no spaces, integer types |

Encode each answer as a named constant at the top of your Flink source.

### Step 2 — Prefer an explicit sort+scan for session-gap logic over `EventTimeSessionWindows` when the grader is strict

`EventTimeSessionWindows.withGap(Time.seconds(T))` in Flink merges two events whose event-time distance is strictly less than `T` and splits when distance is `>= T`. Task specifications frequently mean the opposite ("a stage ends when there is an inactivity period of T minutes" → split when gap `> T`, keep together when gap `<= T`). This one-tick boundary difference is invisible in most spot checks but can misclassify hundreds of sessions when many events land on exact round timestamps.

Recommended pattern for exact-match graders:

```java
// After keyBy(jobId), collect all SUBMIT event-time-micros into a KeyedProcessFunction's
// ListState, register an end-of-time timer, then in onTimer:
//   Sort ascending, scan once, split whenever (t[i] - t[i-1]) > GAP.
// Emit max run length for that job.
```

This makes the boundary convention (`>` vs `>=`) explicit and auditable, and it avoids Flink's implicit window-merge semantics.

If you do use `EventTimeSessionWindows`, verify the boundary experimentally with a synthetic 3-event input (`t=0, t=T, t=2T`) and confirm the number of resulting windows matches the spec.

### Step 3 — Timestamp unit conversion

Google cluster traces store timestamps in **microseconds**. Flink watermarks and window gaps are in **milliseconds**. If you divide µs by 1000 before assigning as the event timestamp, you must also express the gap in milliseconds (`Time.seconds(600)` = 600 000 ms). Never mix. Write a unit-test-style comment near the timestamp assigner recording both units.

### Step 4 — Independent cross-check must NOT reuse your own interpretation

A circular self-check (Python reference that encodes the same misreading as the Flink job) will happily report 0 mismatches while the grader still fails. To break the circularity:

1. Read the task specification twice, once as "strict `>` gap" and once as "non-strict `>=` gap". Implement both variants in the reference script.
2. Read the terminal-event set two ways (FINISH-only vs FINISH+FAIL+KILL+LOST). Compute both filtered outputs.
3. Compare against the Flink output. If any of the 4 combinations matches, you have identified the correct convention; if none matches, look for another axis (unit conversion, deduplication, off-by-one).
4. Only report success when your Flink output matches at least one of the reference variants AND that variant is the one most directly supported by the task text.

### Step 5 — Sanity checks on the emitted file

- `wc -l output` equals the number of jobs with at least one terminal event AND at least one SUBMIT.
- Every line matches regex `^\([0-9]+,[0-9]+\)$` (no spaces, no trailing commas).
- No duplicate job IDs.
- No zero counts (a job with no SUBMITs should not appear).
- Parallelism-1 file sink used for deterministic single-file output.

## Flink Java DataStream — Session/Stage Detection Reference Pattern

Skeleton for the "longest stage per finished job" pattern used in Google cluster-trace style tasks. This is illustrative, not a drop-in.

```java
// Constants derived from Step 1 of the checklist.
final long GAP_MICROS = 600L * 1_000_000L; // 10 min in µs; keep native unit for exactness
final Set<Integer> TERMINAL = Set.of(/* per task text — read carefully */);
final int SUBMIT = 0;

// Task events keyed by jobId, only SUBMITs kept, timestamps left in µs.
DataStream<Tuple2<Long, Long>> submits = taskEvents
    .filter(e -> e.eventType == SUBMIT)
    .map(e -> Tuple2.of(e.jobId, e.timestampMicros))
    .returns(Types.TUPLE(Types.LONG, Types.LONG));

// KeyedProcessFunction that buffers all submit-times, then on end-of-input
// timer sorts and scans with the boundary convention documented in the task.
DataStream<Tuple2<Long, Integer>> perJobLongest = submits
    .keyBy(t -> t.f0)
    .process(new LongestRunFn(GAP_MICROS));  // split when (curr - prev) > GAP_MICROS

// Terminal job events → set of finished job IDs.
DataStream<Long> finished = jobEvents
    .filter(e -> TERMINAL.contains(e.eventType))
    .map(e -> e.jobId);

// Emit only for finished jobs; use a KeyedCoProcessFunction with end-of-time timer.
// Write with FileLineSink at parallelism 1.
```

Inside `LongestRunFn.onTimer`:

```java
List<Long> ts = new ArrayList<>();
listState.get().forEach(ts::add);
if (ts.isEmpty()) return;
Collections.sort(ts);
int best = 1, cur = 1;
for (int i = 1; i < ts.size(); i++) {
    if (ts.get(i) - ts.get(i - 1) > GAP_MICROS) {   // strict > per spec
        cur = 1;
    } else {
        cur++;
    }
    if (cur > best) best = cur;
}
out.collect(Tuple2.of(ctx.getCurrentKey(), best));
```

Use `Long.MAX_VALUE - 1` as the end-of-time event-time timer so bounded sources flush cleanly.

## Key Workflows

### Workflow 1: Build ETL Pipeline

1. Design pipeline architecture (Lambda, Kappa, Medallion).
2. Configure YAML pipeline definition.
3. Generate Airflow DAG with `pipeline_orchestrator.py`.
4. Define data quality validation rules.
5. Deploy and configure monitoring/alerting.

### Workflow 2: Build Real-Time Streaming Pipeline

1. Select streaming architecture (Kappa vs Lambda).
2. Configure streaming pipeline YAML.
3. Generate Kafka configurations.
4. Generate Flink/Spark job scaffolding.
5. Deploy and monitor.

### Workflow 3: Implement a Flink Query for an Exact-Match Grader (NEW)

1. Read the task text and any linked schema PDF twice; complete the Step 1 checklist above.
2. Write POJOs for each event type with explicit CSV column indices (comment the format).
3. Implement a custom gzipped-CSV `SourceFunction` respecting the `AppBase` test-override hooks (`taskSourceOrTest`, `jobSourceOrTest`, `sinkOrTest`).
4. Prefer explicit sort+scan over Flink session windows for gap semantics (Step 2).
5. Use a `FileLineSink` at parallelism 1 for deterministic single-file output.
6. Run the job locally with `mvn dependency:build-classpath` + the shaded jar on classpath.
7. Execute the two-variant cross-check from Step 4 before reporting done.

## Quick Start

### Pipeline Orchestration

```bash
python scripts/pipeline_orchestrator.py --config pipeline_config.yaml --output dags/
python scripts/pipeline_orchestrator.py --config pipeline_config.yaml --validate
python scripts/pipeline_orchestrator.py --template incremental --output dags/
```

### Data Quality Validation

```bash
python scripts/data_quality_validator.py --input data/sales.csv --output report.html
```

### Real-Time Streaming

```bash
python scripts/stream_processor.py --config streaming_config.yaml --validate
python scripts/kafka_config_generator.py --topic user-events --partitions 12 --replication 3 --output kafka/topics/
python scripts/stream_processor.py --config streaming_config.yaml --mode flink --generate --output flink-jobs/
python scripts/streaming_quality_validator.py --lag --consumer-group events-processor --threshold 10000
```

## Core Workflows

See also references for detailed patterns:
- **Frameworks:** [references/frameworks.md](references/frameworks.md)
- **Templates:** [references/templates.md](references/templates.md)
- **Tools:** [references/tools.md](references/tools.md)

## Python Tools

- `pipeline_orchestrator.py` — Airflow DAG generation.
- `data_quality_validator.py` — Multi-dimensional data quality checks.
- `etl_performance_optimizer.py` — Pipeline profiling and recommendations.
- `stream_processor.py` — Streaming pipeline configuration + scaffolding.
- `streaming_quality_validator.py` — Consumer lag, freshness, schema-drift monitoring.
- `kafka_config_generator.py` — Topic/producer/consumer/Streams/Connect configs.

Full docs in [references/tools.md](references/tools.md).

## Tech Stack

- **Languages:** Python 3.8+, SQL, Scala (Spark), Java (Flink)
- **Orchestration:** Apache Airflow, Prefect, Dagster
- **Batch Processing:** Apache Spark, dbt, Pandas
- **Stream Processing:** Apache Kafka, Apache Flink, Kafka Streams, Spark Structured Streaming, AWS Kinesis
- **Storage:** PostgreSQL, BigQuery, Snowflake, Redshift, S3, GCS
- **Schema Management:** Confluent Schema Registry, AWS Glue Schema Registry
- **Containerization:** Docker, Kubernetes
- **Monitoring:** Datadog, Prometheus, Grafana, Kafka UI

## Best Practices

**Pipeline Design:**
1. Idempotent operations for safe reruns.
2. Incremental processing where possible.
3. Clear data lineage and documentation.
4. Comprehensive error handling.
5. Automated recovery mechanisms.

**Data Quality (Exact-Match Graders):**
1. Define quality rules early.
2. Validate at every pipeline stage.
3. NEVER treat a self-implemented reference as ground truth without varying its ambiguous conventions (see Step 4 above).
4. Track quality trends over time.
5. Block bad data from downstream.

**Performance:**
1. Partition large tables by date/region.
2. Use columnar formats (Parquet, ORC).
3. Leverage predicate pushdown.
4. Optimize for your query patterns.
5. Monitor and tune regularly.

**Operations:**
1. Version control everything.
2. Automate testing and deployment.
3. Comprehensive monitoring.
4. Runbooks for incidents.
5. Regular performance reviews.

## Performance Targets

**Batch Pipeline Execution:** P50 < 5 min, P95 < 15 min, success > 99%, freshness < 1 h.
**Streaming Pipeline Execution:** > 10K events/s, P99 end-to-end < 1 s, lag < 10K, exactly-once.
**Data Quality (Batch):** score > 95%, completeness > 99%, timeliness < 2 h.
**Streaming Quality:** freshness P95 < 5 min, late-data < 5%, DLQ < 1%, 100% schema-compatible changes.
**Cost Efficiency:** < $0.10/GB, stable or decreasing cloud cost, > 70% utilization.

## Resources

- **Frameworks Guide:** [references/frameworks.md](references/frameworks.md)
- **Code Templates:** [references/templates.md](references/templates.md)
- **Tool Documentation:** [references/tools.md](references/tools.md)
- **Python Scripts:** `scripts/` directory

---

**Version:** 2.1.0
**Last Updated:** December 16, 2025
**Streaming Enhancement:** Added Flink exact-match grader checklist and session-gap reference pattern.
