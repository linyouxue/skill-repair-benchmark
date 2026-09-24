# Dependency-Surface Audit Before Finalize (Framework/Scaffold Tasks)

**Trigger:** You are implementing a solution inside an existing scaffold (e.g., Flink/Spark job skeleton, shared base class, code generator output) and the prompt/README requires additional packages/classes beyond the main entrypoint.

**Goal:** Ensure the delivered artifact set is complete: all referenced types/resources exist, compile, and are wired so the job produces non-empty, schema-correct output.

## Procedure

### 1) Build the dependency surface inventory
Collect requirements from:
- **Prompt/README**: explicitly required packages/files/classes.
- **Entry points**: main class, runner, base class, factory methods.
- **Imports + symbol references**: types used in code (including fully qualified names).

Create a checklist with these buckets:
- Source decoding/parsing (CSV/JSON/Avro, compression, delimiters)
- Datatypes/POJOs (fields, constructors, getters/setters)
- Event-time (timestamp field, timestamp assigner/watermarks)
- Keys + grouping (key extraction logic)
- State/windowing (window types, allowed lateness)
- Sink schema/output format

### 2) Branch: scaffold expects “POJO-style” datatypes vs generic maps

```python
# Runnable stand-in logic: decide which branch to follow
uses_pojos = True  # set after inspecting scaffold expectations

if uses_pojos:
    print("Branch A: implement POJOs / datatypes with required fields + accessors")
else:
    print("Branch B: implement generic schema (Row/Map) + explicit schema definition")
```

**Branch A (POJOs):**
- Implement missing classes in expected packages.
- Include: no-arg constructor (when needed), field types, getters/setters, `toString`, and `Serializable` where appropriate.
- Ensure parsing utilities populate *all* required fields (especially timestamps).

**Branch B (Row/Map):**
- Define an explicit schema (field names + types).
- Ensure deserialization populates schema-consistent fields.
- Ensure event-time extraction reads the correct field and units.

### 3) Wire into the pipeline
Confirm the pipeline actually uses the new artifacts:
- Source uses the intended parser/deserializer
- Timestamp assigner reads the correct field
- Key selector matches task semantics
- Aggregation output matches required schema

### 4) Verification

```python
# Runnable verification skeleton: treat compile + smoke output as two gates
compile_ok = True   # set after running build tool
smoke_ok = True     # set after a tiny run

if not compile_ok:
    raise SystemExit(
        "Compile failed: re-check the dependency inventory; "
        "add missing classes/resources and fix package names/imports."
    )

if not smoke_ok:
    raise SystemExit(
        "Smoke run produced empty/invalid output: verify parsing + timestamp extraction first, "
        "then verify keying/windowing and sink wiring."
    )

print("Dependency surface verified: compiles and produces non-empty, schema-correct output")
```

**Corrective action on failure:**
- **If compile fails:** re-run step (1), focusing on missing packages/types and mismatched package paths; implement stubs first, then fill fields.
- **If smoke output empty:** re-check parse → timestamp extraction → keying chain; add minimal logging/counters at each stage to find where records drop.
