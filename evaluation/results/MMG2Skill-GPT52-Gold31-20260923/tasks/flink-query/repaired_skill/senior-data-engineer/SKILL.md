---
name: senior-data-engineer
title: Senior Data Engineer Skill Package
description: Implement and debug a Flink DataStream job that sessionizes task SUBMIT
  events per job (10-minute inactivity gap), computes the maximum tasks in any stage,
  and emits results once the job is finished.
domain: engineering
subdomain: data-engineering
difficulty: advanced
time-saved: 'TODO: Quantify time savings'
frequency: 'TODO: Estimate usage frequency'
use-cases:
- Designing data pipelines for ETL/ELT processes
- Building data warehouses and data lakes
- Implementing data quality and governance frameworks
- Creating analytics dashboards and reporting
- Building real-time streaming pipelines with Kafka and Flink
- Implementing exactly-once streaming semantics
- Monitoring streaming quality (consumer lag, data freshness, schema drift)
related-agents: []
related-skills: []
related-commands: []
orchestrated-by: []
dependencies:
  scripts: []
  references: []
  assets: []
compatibility: 'Python 3.8+; platforms: macos, linux, windows'
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
examples:
- title: Example Usage
  input: 'TODO: Add example input for senior-data-engineer'
  output: 'TODO: Add expected output'
stats:
  downloads: 0
  stars: 0
  rating: 0.0
  reviews: 0
version: v2.0.0
author: Claude Skills Team
contributors: []
created: 2025-10-20
updated: 2025-12-16
license: MIT
tags:
- architecture
- data
- design
- engineer
- engineering
- senior
- streaming
- kafka
- flink
- real-time
featured: false
verified: true
---

## Steps
1. Read schema docs (`format.pdf`, `ClusterData2011_2.md`) and implement the required datatypes (e.g., `TaskEvent`, `JobEvent`) under `clusterdata.datatypes` matching the CSV column order and microsecond timestamps.
2. In the Flink job:
   - Ingest a single gzipped CSV shard for task events and job events.
   - Parse events and assign event-time timestamps in **microseconds**; use a watermark strategy appropriate for the input (bounded files).
3. Filter and stage task submissions:
   - Keep only task `SUBMIT` events.
   - `keyBy(jobId)` and build **event-time session “stages”** with a 10-minute inactivity gap (`10 * 60 * 1_000_000` microseconds).
   - Count the number of SUBMIT events per session window.
   - Reduce per `jobId` to the **maximum** session count (longest stage).
4. Emit only when the job is done:
   - From job events, derive a “terminal” signal per `jobId` (include at least `FINISH`, and also treat `KILL` as terminal when present).
   - Join / connect the terminal signal with the computed max-stage count so output is produced “once the job has finished” (jobs with no matching submits in the chosen task shard may legitimately produce `0`).
5. Prevent Flink generic type-erasure runtime failures:
   - If using generic `SourceFunction` / parsing operators (e.g., `GzipCsvSourceFunction<T>`), **add explicit type hints** on the resulting `DataStream` (e.g., `.returns(TaskEvent.class)` / `.returns(JobEvent.class)`) at the point where Flink can’t infer `T`.
6. Write results to the provided `output` path:
   - One tuple per line in exactly: `(jobId,longestStageTaskCount)`
   - Ordering not required.
## Expected Result
The job compiles and runs on Flink without `InvalidTypesException` from generics, and writes a local output file containing one line per jobId with the longest stage’s SUBMIT-count, emitting results only after terminal job completion (including killed jobs).
