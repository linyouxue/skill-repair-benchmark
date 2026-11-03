package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import org.apache.flink.streaming.api.watermark.Watermark;
import org.apache.flink.api.common.functions.AggregateFunction;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.streaming.api.functions.source.SourceFunction;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.streaming.api.windowing.assigners.EventTimeSessionWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.GZIPInputStream;

public class LongestSessionPerJob extends AppBase {

    private static final long END_OF_TIME_TIMER_TS = Long.MAX_VALUE - 1;

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        System.out.println("task_input  " + taskInput);
        System.out.println("job_input  " + jobInput);
        final int sesssize = params.getInt("sesssize", 600);

        if (taskInput == null || jobInput == null || outputPath == null) {
            throw new IllegalArgumentException("Required parameters: task_input, job_input, output");
        }

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        DataStream<TaskEvent> taskEventsStream = env.addSource(
                taskSourceOrTest(new TaskEventSource(taskInput))
        );

        DataStream<JobEvent> jobEventsStream = env.addSource(
                jobSourceOrTest(new JobEventSource(jobInput))
        );

        DataStream<Tuple2<Long, Long>> stageCounts = taskEventsStream
                .filter(e -> e.eventType == TaskEvent.SUBMIT)
                .keyBy(TaskEvent::getJobId)
                .window(EventTimeSessionWindows.withGap(Time.seconds(sesssize)))
                .aggregate(new CountSubmitsAgg(), new SessionCountWindowResult());

        DataStream<JobEvent> terminalJobEvents = jobEventsStream
                .filter(e -> JobEvent.isTerminalEventType(e.eventType));

        DataStream<String> result = stageCounts
                .connect(terminalJobEvents)
                .keyBy(t -> t.f0, JobEvent::getJobId)
                .process(new EmitResultAtEnd());

        result
                .addSink((org.apache.flink.streaming.api.functions.sink.SinkFunction<String>) sinkOrTest(new LocalFileSink(outputPath)))
                .setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    private static final class TaskEventSource extends GzippedCsvSource<TaskEvent> {

        private TaskEventSource(String path) {
            super(path);
        }

        @Override
        protected TaskEvent parse(String line) {
            String[] cols = line.split(",", -1);
            if (cols.length < 6) {
                return null;
            }
            if (cols[0].isEmpty() || cols[2].isEmpty() || cols[5].isEmpty()) {
                return null;
            }

            long tsMs = Long.parseLong(cols[0]) / 1_000L;
            long jobId = Long.parseLong(cols[2]);
            int eventType = Integer.parseInt(cols[5]);
            return new TaskEvent(tsMs, jobId, eventType);
        }

        @Override
        protected long eventTimestamp(TaskEvent value) {
            return value.timestamp;
        }
    }

    private static final class JobEventSource extends GzippedCsvSource<JobEvent> {

        private JobEventSource(String path) {
            super(path);
        }

        @Override
        protected JobEvent parse(String line) {
            String[] cols = line.split(",", -1);
            if (cols.length < 4) {
                return null;
            }
            if (cols[0].isEmpty() || cols[2].isEmpty() || cols[3].isEmpty()) {
                return null;
            }

            long tsMs = Long.parseLong(cols[0]) / 1_000L;
            long jobId = Long.parseLong(cols[2]);
            int eventType = Integer.parseInt(cols[3]);
            return new JobEvent(tsMs, jobId, eventType);
        }

        @Override
        protected long eventTimestamp(JobEvent value) {
            return value.timestamp;
        }
    }

    private abstract static class GzippedCsvSource<T> implements SourceFunction<T> {

        private final String path;
        private volatile boolean running = true;

        protected GzippedCsvSource(String path) {
            this.path = path;
        }

        protected abstract T parse(String line);

        protected abstract long eventTimestamp(T value);

        @Override
        public void run(SourceContext<T> ctx) throws Exception {
            long lastWatermark = Long.MIN_VALUE;
            Path p = Path.of(path);

            try (InputStream raw = Files.newInputStream(p);
                 InputStream in = path.endsWith(".gz") ? new GZIPInputStream(raw) : raw;
                 BufferedReader br = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {

                String line;
                while (running && (line = br.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }

                    T value;
                    try {
                        value = parse(line);
                    } catch (Exception ignored) {
                        continue;
                    }

                    if (value == null) {
                        continue;
                    }

                    long ts = eventTimestamp(value);
                    synchronized (ctx.getCheckpointLock()) {
                        ctx.collectWithTimestamp(value, ts);
                        if (ts > lastWatermark) {
                            ctx.emitWatermark(new Watermark(ts));
                            lastWatermark = ts;
                        }
                    }
                }
            }

            synchronized (ctx.getCheckpointLock()) {
                ctx.emitWatermark(Watermark.MAX_WATERMARK);
            }
        }

        @Override
        public void cancel() {
            running = false;
        }
    }

    private static final class CountSubmitsAgg implements AggregateFunction<TaskEvent, Long, Long> {

        @Override
        public Long createAccumulator() {
            return 0L;
        }

        @Override
        public Long add(TaskEvent value, Long accumulator) {
            return accumulator + 1L;
        }

        @Override
        public Long getResult(Long accumulator) {
            return accumulator;
        }

        @Override
        public Long merge(Long a, Long b) {
            return a + b;
        }
    }

    private static final class SessionCountWindowResult extends ProcessWindowFunction<Long, Tuple2<Long, Long>, Long, TimeWindow> {

        @Override
        public void process(Long key, Context context, Iterable<Long> elements, Collector<Tuple2<Long, Long>> out) {
            Long cnt = elements.iterator().next();
            out.collect(Tuple2.of(key, cnt));
        }
    }

    private static final class EmitResultAtEnd extends KeyedCoProcessFunction<Long, Tuple2<Long, Long>, JobEvent, String> {

        private transient ValueState<Long> maxStage;
        private transient ValueState<Boolean> hasTerminalEvent;
        private transient ValueState<Boolean> endTimerRegistered;

        @Override
        public void open(Configuration parameters) {
            maxStage = getRuntimeContext().getState(new ValueStateDescriptor<>("maxStage", Long.class));
            hasTerminalEvent = getRuntimeContext().getState(new ValueStateDescriptor<>("hasTerminalEvent", Boolean.class));
            endTimerRegistered = getRuntimeContext().getState(new ValueStateDescriptor<>("endTimerRegistered", Boolean.class));
        }

        @Override
        public void processElement1(Tuple2<Long, Long> stageCount, Context ctx, Collector<String> out) throws Exception {
            Long currentMax = maxStage.value();
            long v = stageCount.f1 == null ? 0L : stageCount.f1;
            if (currentMax == null || v > currentMax) {
                maxStage.update(v);
            }
            ensureEndTimerRegistered(ctx);
        }

        @Override
        public void processElement2(JobEvent value, Context ctx, Collector<String> out) throws Exception {
            hasTerminalEvent.update(true);
            ensureEndTimerRegistered(ctx);
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<String> out) throws Exception {
            Boolean terminal = hasTerminalEvent.value();
            if (terminal != null && terminal) {
                Long m = maxStage.value();
                if (m == null) {
                    m = 0L;
                }
                out.collect("(" + ctx.getCurrentKey() + "," + m + ")");
            }

            maxStage.clear();
            hasTerminalEvent.clear();
            endTimerRegistered.clear();
        }

        private void ensureEndTimerRegistered(Context ctx) throws Exception {
            Boolean registered = endTimerRegistered.value();
            if (registered == null || !registered) {
                ctx.timerService().registerEventTimeTimer(END_OF_TIME_TIMER_TS);
                endTimerRegistered.update(true);
            }
        }
    }

    private static final class LocalFileSink extends RichSinkFunction<String> {

        private final String outputPath;
        private transient BufferedWriter writer;

        private LocalFileSink(String outputPath) {
            this.outputPath = outputPath;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            Path p = Path.of(outputPath);
            Path parent = p.getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }
            writer = Files.newBufferedWriter(p, StandardCharsets.UTF_8);
        }

        @Override
        public synchronized void invoke(String value, Context context) throws Exception {
            writer.write(value);
            writer.newLine();
        }

        @Override
        public void close() throws Exception {
            if (writer != null) {
                writer.flush();
                writer.close();
            }
        }
    }
}
