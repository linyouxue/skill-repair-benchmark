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
version: v2.0.1
author: Claude Skills Team
contributors: []
created: 2025-10-20
updated: 2026-11-25
license: MIT

# === DISCOVERABILITY ===
tags: [architecture, data, design, engineer, engineering, senior, streaming, kafka, flink, real-time]
featured: false
verified: true
---

# Senior Data Engineer

## Core Capabilities

- **Batch Pipeline Orchestration** - Design and implement production-ready ETL/ELT pipelines with Airflow, intelligent dependency resolution, retry logic, and comprehensive monitoring
- **Real-Time Streaming** - Build event-driven streaming pipelines with Kafka, Flink, Kinesis, and Spark Streaming with exactly-once semantics and sub-second latency
- **Data Quality Management** - Comprehensive batch and streaming data quality validation covering completeness, accuracy, consistency, timeliness, and validity
- **Streaming Quality Monitoring** - Track consumer lag, data freshness, schema drift, throughput, and dead letter queue rates for streaming pipelines
- **Performance Optimization** - Analyze and optimize pipeline performance with query optimization, Spark tuning, and cost analysis recommendations

## Critical Addendum: Output-Contract & Filtering Checklist (Streaming/Batch Analytics)

When implementing analytics jobs (Flink/Spark/SQL) that produce **one output row per entity** (e.g., per jobId/userId/sessionId), failures often come from **contract violations** (extra/missing entities) rather than aggregation math.

Before coding and again before final output, perform this checklist and make it explicit in code:

1. **Define the output domain precisely**
   - What entities must appear?
   - What entities must be excluded?
   - Are “empty” entities allowed (e.g., outputting 0 when there are no events), or must they be omitted?

2. **Identify the authoritative event(s) that gate inclusion**
   - If the task says “once X has finished/closed”, require an explicit terminal event (e.g., `FINISH`) or a clearly defined completion condition.
   - Do **not** infer completion from inactivity unless the task explicitly defines that as completion.

3. **Filter early, but gate output late**
   - Filter to relevant event types early (e.g., only `SUBMIT` for stage/sessionization).
   - Gate output late using the completion condition (e.g., join/side-input of finished IDs) so you don’t emit partial or non-terminal entities.

4. **Make exclusion rules executable**
   - Add code-level checks such as:
     - `finishedIds.contains(key)` before emitting.
     - `if (noRelevantEvents) then (omit OR emit default)` according to the contract.

5. **Add a “contract sanity” validation step** (even if only in local debug)
   - Compare the set of emitted IDs against the expected domain (e.g., finished IDs).
   - If mismatch is possible, log counts: `emitted`, `eligible`, `excluded`.

This checklist is intentionally generic and applies across datasets/tasks.

## Key Workflows

### Workflow 1: Build ETL Pipeline

**Time:** 2-4 hours

**Steps:**
1. Design pipeline architecture using Lambda, Kappa, or Medallion pattern
2. Configure YAML pipeline definition with sources, transformations, targets
3. Generate Airflow DAG with `pipeline_orchestrator.py`
4. Define data quality validation rules
5. Deploy and configure monitoring/alerting

**Expected Output:** Production-ready ETL pipeline with 99%+ success rate, automated quality checks, and comprehensive monitoring

### Workflow 2: Build Real-Time Streaming Pipeline

**Time:** 3-5 days

**Steps:**
1. Select streaming architecture (Kappa vs Lambda) based on requirements
2. Configure streaming pipeline YAML (sources, processing, sinks, quality)
3. Generate Kafka configurations with `kafka_config_generator.py`
4. Generate Flink/Spark job scaffolding with `stream_processor.py`
5. Deploy and monitor with `streaming_quality_validator.py`

**Expected Output:** Streaming pipeline processing 10K+ events/sec with P99 latency < 1s, exactly-once delivery, and real-time quality monitoring

### Workflow 3: Flink Event-Time Sessionization + Terminal Gating (Pattern)

Use this workflow when you need to:
- group events per key into **sessions/stages** based on an inactivity gap in **event time**, and
- emit results **only for keys that meet a terminal condition** (e.g., entity finished/closed).

**Steps:**
1. **Normalize timestamps and event time**
   - Convert source timestamps into a consistent unit (ms recommended for Flink event time).
   - Assign timestamps + watermarks.

2. **Filter to relevant event types for sessionization**
   - Example: only events that define activity (e.g., `SUBMIT`).

3. **Sessionize per key**
   - Use event-time session windows with a gap (e.g., 10 minutes).
   - Aggregate per session (e.g., count events/tasks in the session).

4. **Reduce per key to the maximum session metric**
   - Example: max session size per key.

5. **Compute terminal eligibility set**
   - From a separate stream/table of terminal events (e.g., `FINISH`), derive the set of eligible keys.

6. **Gate output by eligibility**
   - Join/filter so only eligible keys are emitted.
   - Decide what to do for eligible keys with no relevant events (omit vs default) based on the task contract.

7. **Write output in the required format**
   - Ensure formatting and one-line-per-record output.

This pattern prevents “unexpected entities” from being emitted.

## Overview

This skill provides comprehensive expertise in data engineering fundamentals through advanced production patterns. From designing medallion architectures to implementing real-time streaming pipelines, it covers the full spectrum of modern data engineering including ETL/ELT design, data quality frameworks, pipeline orchestration, and DataOps practices.

**What This Skill Provides:**
- Production-ready pipeline templates (Airflow, Spark, dbt)
- Comprehensive data quality validation framework
- Performance optimization and cost analysis tools
- Data architecture patterns (Lambda, Kappa, Medallion)
- Complete DataOps CI/CD workflows

**Best For:**
- Building scalable data pipelines for enterprise systems
- Implementing data quality and governance frameworks
- Optimizing ETL performance and cloud costs
- Designing modern data architectures (lake, warehouse, lakehouse)
- Production ML/AI data infrastructure

## Quick Start

### Pipeline Orchestration

```bash
# Generate Airflow DAG from configuration
python scripts/pipeline_orchestrator.py --config pipeline_config.yaml --output dags/

# Validate pipeline configuration
python scripts/pipeline_orchestrator.py --config pipeline_config.yaml --validate

# Use incremental load template
python scripts/pipeline_orchestrator.py --template incremental --output dags/
```

### Data Quality Validation

```bash
# Validate CSV file with quality checks
python scripts/data_quality_validator.py --input data/sales.csv --output report.html

# Validate database table with custom rules
python scripts/data_quality_validator.py \
    --connection postgresql://user:pass@host/db \
    --table sales_transactions \
    --rules rules/sales_validation.yaml \
    --threshold 0.95
```

### Performance Optimization

```bash
# Analyze pipeline performance and get recommendations
python scripts/etl_performance_optimizer.py \
    --airflow-db postgresql://host/airflow \
    --dag-id sales_etl_pipeline \
    --days 30 \
    --optimize

# Analyze Spark job performance
python scripts/etl_performance_optimizer.py \
    --spark-history-server http://spark-history:18080 \
    --app-id app-20250115-001
```

### Real-Time Streaming

```bash
# Validate streaming pipeline configuration
python scripts/stream_processor.py --config streaming_config.yaml --validate

# Generate Kafka topic and client configurations
python scripts/kafka_config_generator.py \
    --topic user-events \
    --partitions 12 \
    --replication 3 \
    --output kafka/topics/

# Generate exactly-once producer configuration
python scripts/kafka_config_generator.py \
    --producer \
    --profile exactly-once \
    --output kafka/producer.properties

# Generate Flink job scaffolding
python scripts/stream_processor.py \
    --config streaming_config.yaml \
    --mode flink \
    --generate \
    --output flink-jobs/

# Monitor streaming quality
python scripts/streaming_quality_validator.py \
    --lag --consumer-group events-processor --threshold 10000 \
    --freshness --topic processed-events --max-latency-ms 5000 \
    --output streaming-health-report.html
```

## Reference Documentation

See:
- **Frameworks:** `references/frameworks.md`
- **Templates:** `references/templates.md`
- **Tools:** `references/tools.md`

---

**Version:** 2.0.1
**Last Updated:** November 25, 2026
