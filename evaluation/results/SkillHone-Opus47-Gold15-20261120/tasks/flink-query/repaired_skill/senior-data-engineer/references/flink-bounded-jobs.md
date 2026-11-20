# Bounded Flink Jobs on Historical / File Data

Guidance for building Flink `DataStream` jobs that process **bounded** inputs
(for example gzipped CSV dumps of event traces) and must produce one final
result per key. This complements the Kafka-oriented templates in
[templates.md](templates.md) and the streaming patterns in
[frameworks.md](frameworks.md).

Use this reference when the task looks like:

- "Read one or more compressed CSV files of events and compute a per-entity
  aggregation."
- "Group events into sessions by inactivity gap and find the largest / longest
  session per entity."
- "Only emit a result for an entity once some completion event for that entity
  is seen."
- "Write one line per result to a local output file."

The patterns below are deliberately generic. **Do not hard-code column
indices, event-type integer codes, timestamp units, session gaps, or output
formats** — read them from the task prompt and the dataset's own schema
documentation (an accompanying schema PDF, README, JSON/Avro schema, or similar).

---

## 1. Start from the dataset schema, not from assumptions

Before writing code:

1. **Open the dataset's schema document** (PDF, README, JSON schema, Avro
   schema, etc.) and record, in comments in your POJO class:
   - The **ordered column list** for each file type.
   - The **units** of every timestamp column (seconds? milliseconds?
     microseconds? nanoseconds?).
   - The **enumeration of event-type / status codes** and, crucially, which
     codes correspond to the semantic categories the task's prompt
     mentions. Do **not** guess from the column name or by inspecting a
     few rows — look the codes up in the schema document.
   - Which columns can be **empty** (CSV blank fields) and which are
     mandatory.
2. When the prompt mentions a specific event-type category, copy the
   schema's definition into your POJO as named constants and reference the
   constants by name everywhere. This both documents the choice and makes
   it reviewable. Match whatever category the prompt names — do not expand
   the set ("terminal"/"any-non-running"/etc.) or shrink it unless the
   prompt says so.
3. If the schema document is a PDF or binary, extract the text first (see the
   `pdf` skill). **Prefer the schema document over sampling rows of the CSV.**

Common failure mode: inferring that an event-type code is `0` (or some
"obvious" default) when the schema actually defines each category as a
specific code that may or may not match the guess. Getting this wrong
silently changes which rows are counted and which keys are considered
eligible for output. A closely related failure is treating "the key has
finished" as "any terminal state" when the prompt actually names one
specific completion category; include exactly the codes the prompt names.

---

## 2. Reading gzipped CSV as a bounded source

Flink's `env.readTextFile(path)` does not transparently decompress `.gz`, and
the built-in `FileSource` text formats do not either in Flink 1.17/1.18 without
a custom `BulkFormat`. The simplest portable option is a tiny
`SourceFunction<T>` that streams `GZIPInputStream` line by line and emits
parsed POJOs:

```java
public class GzipCsvSource<T> implements SourceFunction<T> {
    private final String path;
    private final java.util.function.Function<String, T> parse; // return null to skip
    private volatile boolean running = true;

    public GzipCsvSource(String path, java.util.function.Function<String, T> parse) {
        this.path = path;
        this.parse = parse;
    }

    @Override
    public void run(SourceContext<T> ctx) throws Exception {
        try (java.io.InputStream fis = new java.io.FileInputStream(path);
             java.io.InputStream gis = new java.util.zip.GZIPInputStream(fis);
             java.io.BufferedReader br = new java.io.BufferedReader(
                     new java.io.InputStreamReader(gis, java.nio.charset.StandardCharsets.UTF_8))) {
            String line;
            while (running && (line = br.readLine()) != null) {
                T event = parse.apply(line);
                if (event != null) ctx.collect(event);
            }
        }
    }

    @Override
    public void cancel() { running = false; }
}
```

Keep CSV parsing defensive:

- `line.split(",", -1)` so trailing empty fields are preserved.
- Treat empty strings explicitly (`parts[i].isEmpty()`) rather than letting
  `Long.parseLong("")` throw.
- Return `null` on malformed lines and skip them, so one bad row cannot abort
  the whole job.

If `AppBase` (or an equivalent harness base class) provides a
`...sourceOrTest(...)` method, call it so test harnesses can inject their own
bounded sources without code changes:

```java
env.addSource(AppBase.sourceOrTest(new GzipCsvSource<>(inputPath, MyEvent::parse)))
   .returns(MyEvent.class);
```

---

## 3. Event-time watermarks for microsecond (or non-millisecond) timestamps

Flink's event-time APIs are millisecond-based. If the dataset timestamps are
in **microseconds, nanoseconds, or seconds**, convert them in a single
helper method on the POJO (e.g. `getTimestampMillis()`), and only use that
helper when assigning timestamps:

```java
.assignTimestampsAndWatermarks(
    WatermarkStrategy.<MyEvent>forBoundedOutOfOrderness(Duration.ofSeconds(5))
        .withTimestampAssigner((e, ts) -> e.getTimestampMillis()))
```

- If the source file is already sorted by event time, a very small
  out-of-orderness (e.g. 1–5 s) is enough.
- The same conversion must be used **consistently** for session gap
  arithmetic; mixing micros and millis is a frequent off-by-1000× bug.

---

## 4. Session windows + per-key aggregation

For "group events close together in event time per key":

```java
DataStream<Tuple2<Key, Integer>> sessionCounts = events
    .filter(e -> e.getKind() == MyEvent.ACTIVITY)      // whatever the prompt means
    .assignTimestampsAndWatermarks(wmStrategy)
    .keyBy(e -> e.getKey())
    .window(EventTimeSessionWindows.withGap(Time.seconds(gapSeconds)))
    .process(new CountPerSession());
```

Make the gap configurable (via whatever CLI flag the skeleton exposes) with
the task-specified default, and document the unit in the CLI help.

Use `ProcessWindowFunction` if you need the key or window metadata; use
`AggregateFunction` for larger windows where incremental aggregation matters.

---

## 5. "Longest / largest result per key" — correct emission discipline

When the goal is **one final tuple per key** (max, sum, longest session,
etc.), a naive `keyBy(key).maxBy(count)` followed by immediate sinking emits
a **running maximum** — one output per input, not one output per key. Even
worse, if a downstream `KeyedCoProcessFunction` emits the first value it sees
and then marks the key "done", the final result will systematically
undercount keys whose maximum arrives late.

### Anti-pattern (do NOT do this)

```java
// BUG: tryEmit will fire as soon as *both* states are first populated,
// which is usually BEFORE the per-key maximum has been seen.
public void processElement1(Tuple2<K, V> value, Context ctx, Collector<String> out) {
    Integer cur = maxState.value();
    if (cur == null || value.f1 > cur) maxState.update(value.f1);
    tryEmit(ctx.getCurrentKey(), out);  // <-- emits too early
}
public void processElement2(K key, Context ctx, Collector<String> out) {
    finishedState.update(true);
    tryEmit(ctx.getCurrentKey(), out);  // <-- emits too early
}
```

### Correct pattern — emit only in `onTimer`

Buffer all per-key signals in Flink state and emit **only once**, when you
know no further input will arrive for the key. For bounded input, this is
exactly when Flink drives the watermark to `Long.MAX_VALUE` at end-of-input,
so register a one-shot timer just before that:

```java
public class EmitOnCompletion<K, V>
        extends KeyedCoProcessFunction<K, Tuple2<K, V>, K, String> {

    private transient ValueState<V>       bestState;       // e.g. running max
    private transient ValueState<Boolean> completedState;  // "finish" seen
    private transient ValueState<Boolean> timerRegistered;

    @Override public void open(Configuration c) {
        bestState       = getRuntimeContext().getState(new ValueStateDescriptor<>("best", ...));
        completedState  = getRuntimeContext().getState(new ValueStateDescriptor<>("completed", Boolean.class));
        timerRegistered = getRuntimeContext().getState(new ValueStateDescriptor<>("timer", Boolean.class));
    }

    private void registerFlushTimer(Context ctx) throws Exception {
        if (!Boolean.TRUE.equals(timerRegistered.value())) {
            // On bounded input Flink pushes the watermark to Long.MAX_VALUE
            // at end-of-input; MAX_VALUE - 1 ensures the timer fires.
            ctx.timerService().registerEventTimeTimer(Long.MAX_VALUE - 1);
            timerRegistered.update(true);
        }
    }

    @Override
    public void processElement1(Tuple2<K, V> v, Context ctx, Collector<String> out) throws Exception {
        V cur = bestState.value();
        if (cur == null || isBetter(v.f1, cur)) bestState.update(v.f1);
        registerFlushTimer(ctx);
        // DO NOT emit here.
    }

    @Override
    public void processElement2(K key, Context ctx, Collector<String> out) throws Exception {
        completedState.update(true);
        registerFlushTimer(ctx);
        // DO NOT emit here.
    }

    @Override
    public void onTimer(long t, OnTimerContext ctx, Collector<String> out) throws Exception {
        V best = bestState.value();
        if (Boolean.TRUE.equals(completedState.value()) && best != null) {
            out.collect(format(ctx.getCurrentKey(), best));
        }
    }
}
```

Rules of thumb for this family of jobs:

- **Only emit at end-of-input** (via the `Long.MAX_VALUE - 1` timer), never
  on individual element arrivals, when the correct answer is a function of
  **all** elements for the key.
- The "completion signal" side is only a **filter** on which keys to emit,
  not a trigger to emit immediately.
- If instead the task really does want the "latest known value after each
  update", then running-max via `maxBy(...)` into the sink is correct — but
  double-check against the prompt wording.

---

## 6. Single-file local output

The task often says "write one line per tuple to a local file". `writeAsText`
and `FileSink` both write *directories* of part-files at `parallelism > 1`.
Guarantee a single plain output file with a simple sink:

```java
public class FileLineSink extends RichSinkFunction<String> {
    private final String path;
    private transient BufferedWriter writer;
    public FileLineSink(String path) { this.path = path; }

    @Override public void open(Configuration c) throws Exception {
        java.io.File f = new java.io.File(path);
        java.io.File p = f.getParentFile();
        if (p != null && !p.exists()) p.mkdirs();
        writer = new BufferedWriter(new FileWriter(f, false));
    }
    @Override public void invoke(String value, Context ctx) throws Exception {
        writer.write(value); writer.newLine();
    }
    @Override public void close() throws Exception {
        if (writer != null) { writer.flush(); writer.close(); }
    }
}
```

Combine with `env.setParallelism(1)` for the final write stage (or
`output.setParallelism(1)` locally) so you get exactly one file at exactly
the path the prompt asked for, and so the `RichSinkFunction` is not run more
than once.

If the harness supplies a test sink via `AppBase.sinkOrTest(...)`, honour it
instead of hard-wiring `FileLineSink`.

---

## 7. Output format discipline

Match the prompt's example exactly:

- Delimiters: parentheses, commas, tabs, or newlines — copy literally,
  including whether there is a space after the comma.
- Numeric formatting: do not quote integers; do not emit scientific notation
  for large longs.
- No header line, no trailing blank line, unless the prompt says otherwise.
- Line endings: plain `\n`.

A safe pattern is a single `format(...)` method on your final POJO/tuple so
the whole job uses one source of truth for the output line.

---

## 8. Build & run checklist

- `pom.xml` usually declares Flink (`flink-streaming-java`, `flink-clients`,
  `flink-java`) as `provided`. For a local smoke test, run with the full
  Maven classpath appended:
  ```bash
  mvn -q dependency:build-classpath -Dmdep.outputFile=/tmp/cp.txt
  java --add-opens java.base/java.util=ALL-UNNAMED \
       --add-opens java.base/java.lang=ALL-UNNAMED \
       --add-opens java.base/java.lang.reflect=ALL-UNNAMED \
       -cp "target/<your-shaded-jar>.jar:$(cat /tmp/cp.txt)" \
       <fully.qualified.MainClass> --input-a ... --input-b ... --output ...
  ```
- Keep `env.setParallelism(1)` for local correctness checks; only raise the
  parallelism once the single-threaded result matches expectations.
- Verify count-level correctness against an independent, minimal Python
  (or shell) reference on a **small** input slice — but remember a matching
  reference only validates that the Flink *implementation* matches the
  *reference*, not that either matches the task's semantic intent. Re-read
  the prompt once more to confirm:
  - The meaning of each event-type category the prompt names (which exact
    code or codes from the schema?).
  - Whether a "completion" / "has finished" signal is one specific category
    or any of several — mirror the prompt, nothing more, nothing less.
  - The expected output format.

---

## 9. Review checklist before declaring done

- [ ] Column indices and event-type codes come from the dataset's own schema
      doc, not from heuristics.
- [ ] Timestamp unit conversion is centralised in one helper and used
      everywhere (never mixed).
- [ ] Session-gap, timestamp unit, and output format match the prompt verbatim.
- [ ] The per-key final result is emitted **only once**, via a timer at
      end-of-input, not on each state update.
- [ ] Completion-signal side only gates emission; it does not trigger it
      prematurely.
- [ ] Local output is a single file at the exact path, one line per result.
- [ ] `AppBase.*OrTest(...)` methods are used where provided, so a test
      harness can swap sources/sinks without editing your code.
- [ ] Job executes on a bounded run to completion with the correct
      end-of-input watermark semantics (no missing keys, no duplicates).
