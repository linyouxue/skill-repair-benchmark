---
name: senior-data-engineer
title: Senior Data Engineer Skill Package
description: Build reliable data pipelines by translating prompts into precise dataflow semantics, implementing correct stateful/event-time logic, and verifying completeness with compile/smoke-run and evidence-based checks.
domain: engineering
subdomain: data-engineering

difficulty: advanced
time-saved: "TODO: Quantify time savings"
frequency: "TODO: Estimate usage frequency"
use-cases:
  - Designing data pipelines for ETL/ELT processes
  - Building data warehouses and data data lakes
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

tags: [architecture, data, design, engineer, engineering, senior, streaming, kafka, flink, real-time]
featured: false
verified: true
version: v2.0.4
author: Claude Skills Team
contributors: []
created: 2025-10-20
updated: 2026-09-23
license: MIT
---
# Senior Data Engineer

## Key Workflows

### Workflow 0: Verify Evidence Is Accessible Before Diagnosing or Proposing Changes

**Goal:** Avoid attributing failures to design/code when run artifacts (trace, verifier logs, outputs) are missing, empty, or outside sandbox-readable paths.

**Steps:**
1. Confirm required artifacts exist and are non-empty (execution trace, produced outputs, verifier logs).
2. Confirm every referenced evidence path is under the sandbox-allowed project root.
3. If a referenced path is absolute or outside the project root, **map it to the run’s exported in-root directories** (commonly `.../batch/<task>/workspace/` for sources and `.../iter_<N>/` for trace/assessment artifacts) before reading.
4. If a read fails due to sandbox/missing path, **stop retrying the same path**; instead, list/search within the allowed root to locate the corresponding artifact, then continue diagnosis only once stdout/stderr/output/result files are readable.

**Expected Output:** Either (a) accessible evidence that supports diagnosis, or (b) a clear “insufficient evidence / harness export issue” stop with the concrete artifact-export fix needed.

### Workflow 1: Dependency-Surface Audit Before Finalize

**Goal:** When implementing within an existing scaffold/framework, ensure you deliver *all* required supporting code (datatypes/POJOs/parsers/config) and that it compiles and produces non-empty output.

**Steps:**
1. Inventory requirements from three places: task prompt/README, imports/references in edited files, and the framework/base class entry points.
2. Enumerate the “dependency surface”: every referenced type, package, resource file, serializer/deserializer, schema, and output sink.
3. Create or update missing supporting artifacts (e.g., POJOs under an expected package, parsing utilities, timestamp extractors, getters/setters).
4. Wire artifacts into the pipeline (the right source format, timestamp assignment, key extraction, windowing/aggregation, and sink schema).
5. Compile/package locally (e.g., `mvn -q test` or `mvn -q package` for JVM projects) before final output.
6. Smoke run on a minimal input (or local mini-cluster mode) and verify the sink is non-empty and schema-correct.

Read references/dependency-surface-audit.md when you are implementing code into a provided scaffold/base class and the prompt specifies additional required files or packages.
Skip when the task is a single-file script with no external framework hooks.

## Operation: Event-Time Sessionization / “Stage” Detection in Streaming Jobs

When a task requires inactivity-based sessions/stages, enforce the spec by turning it into a *pre-coding* checklist and then implementing it literally.

```python
# Semantics checklist (keep as variables you can verify in code review)
key_field = "entity_id"               # gap applies per this entity
selected_event_type = "TYPE_A"        # filter to this subset

# Always write the *input* timestamp unit and convert explicitly
input_time_unit = "micros"            # seconds | millis | micros
inactivity_gap_seconds = 10 * 60

gap_in_input_units = inactivity_gap_seconds * (
    1_000_000 if input_time_unit == "micros" else 1_000 if input_time_unit == "millis" else 1
)
assert gap_in_input_units > 0

# Two-level aggregation reminder: per-session metric -> per-entity reduction
session_metric = "count_events"
per_entity_reduce = "max_over_sessions"
```

Decision rule: If the task mentions *event time*, *watermarks*, *timestamp units*, or “longest session/stage,” treat any implementation that omits (a) pre-filtering, (b) explicit unit conversion, or (c) the required two-level aggregation as wrong until proven otherwise.

Read references/event-time-sessionization.md when the prompt mentions inactivity gaps/sessions/stages, event time, watermarks, timestamp units, or a “per-stage then max-per-entity” metric.
Skip when the task is pure processing-time or batch SQL with explicit grouping boundaries.

## Operation: Building Real-Time Streaming Pipelines

Apply a streaming architecture (Kappa/Lambda) and ensure the pipeline is correct end-to-end: event-time semantics, schema/contract, state, and sinks.

```python
# Generic validation skeleton: schema + smoke output checks
required_fields = {"key", "event_time"}
assert required_fields.issubset(record.keys())

# After running a small sample, verify sink has expected schema and >0 rows
output_rows = read_output_rows()
assert len(output_rows) > 0
assert required_fields.issubset(output_rows[0].keys())
```

Decision rule: If the pipeline depends on framework-provided datatypes/parsers, perform a dependency-surface audit before tuning correctness/performance.

## Common Pitfalls

- Implementing event-time sessionization with the wrong semantics (processing time vs event time, wrong key, missing pre-filter, missing two-level aggregation, wrong count semantics, or wrong timestamp units), yielding deterministically wrong aggregates.
- Implementing only the top-level job while missing required supporting artifacts (POJOs/parsers/schema/timestamp extraction), causing compile failures or empty outputs.
- Debugging logic without first confirming evidence/trace artifacts are accessible within the sandbox-allowed project root.
