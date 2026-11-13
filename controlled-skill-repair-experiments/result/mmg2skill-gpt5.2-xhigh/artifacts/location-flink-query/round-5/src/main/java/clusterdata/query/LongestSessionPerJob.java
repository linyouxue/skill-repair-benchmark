package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.streaming.api.functions.source.RichSourceFunction;
import org.apache.flink.util.Collector;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.time.Duration;
import java.util.zip.GZIPInputStream;

public class LongestSessionPerJob extends AppBase {

    private static final int SUBMIT = 0;
    private static final int FINISH = 1;

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        final int sesssize = params.getInt("sesssize", 600);

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        if (AppBase.taskEvents == null && taskInput == null) {
            throw new IllegalArgumentException("Missing required parameter: task_input");
        }
        if (AppBase.jobEvents == null && jobInput == null) {
            throw new IllegalArgumentException("Missing required parameter: job_input");
        }
        if (AppBase.out == null && outputPath == null) {
            throw new IllegalArgumentException("Missing required parameter: output");
        }

        long gapMicros = sesssize * 1_000_000L;

        WatermarkStrategy<TaskEvent> taskWatermarks = WatermarkStrategy
                .<TaskEvent>forMonotonousTimestamps()
                .withTimestampAssigner((event, timestamp) -> event.timestamp)
                .withIdleness(Duration.ofSeconds(5));

        WatermarkStrategy<JobEvent> jobWatermarks = WatermarkStrategy
                .<JobEvent>forMonotonousTimestamps()
                .withTimestampAssigner((event, timestamp) -> event.timestamp)
                .withIdleness(Duration.ofSeconds(5));

        DataStream<TaskEvent> taskEventsStream = env
                .addSource(taskSourceOrTest(new TaskEventSource(taskInput)))
                .assignTimestampsAndWatermarks(taskWatermarks);

        DataStream<JobEvent> jobEventsStream = env
                .addSource(jobSourceOrTest(new JobEventSource(jobInput)))
                .assignTimestampsAndWatermarks(jobWatermarks);

        DataStream<StageEvent> submitEvents = taskEventsStream
                .filter(TaskEvent::isSubmit)
                .map(event -> new StageEvent(event.jobId, SUBMIT))
                .returns(StageEvent.class);

        DataStream<StageEvent> finishEvents = jobEventsStream
                .filter(JobEvent::isFinish)
                .map(event -> new StageEvent(event.jobId, FINISH))
                .returns(StageEvent.class);

        DataStream<String> results = submitEvents
                .union(finishEvents)
                .keyBy(event -> event.jobId)
                .process(new LongestStagePerJobProcessFunction(gapMicros));

        @SuppressWarnings("unchecked")
        org.apache.flink.streaming.api.functions.sink.SinkFunction<String> sink =
                (org.apache.flink.streaming.api.functions.sink.SinkFunction<String>) sinkOrTest(new LocalFileSink(outputPath));

        results.addSink(sink).setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    public static class StageEvent {
        public long jobId;
        public int kind;

        public StageEvent() {}

        public StageEvent(long jobId, int kind) {
            this.jobId = jobId;
            this.kind = kind;
        }

        public boolean isSubmit() {
            return kind == SUBMIT;
        }

        public boolean isFinish() {
            return kind == FINISH;
        }
    }

    private static class LongestStagePerJobProcessFunction extends KeyedProcessFunction<Long, StageEvent, String> {

        private final long gapMicros;

        private transient ValueState<Long> lastSubmitTimestamp;
        private transient ValueState<Long> currentStageCount;
        private transient ValueState<Long> maxStageCount;
        private transient ValueState<Long> finishTimestamp;

        private LongestStagePerJobProcessFunction(long gapMicros) {
            this.gapMicros = gapMicros;
        }

        @Override
        public void open(Configuration parameters) {
            lastSubmitTimestamp = getRuntimeContext().getState(new ValueStateDescriptor<>("lastSubmitTimestamp", Long.class));
            currentStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("currentStageCount", Long.class));
            maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Long.class));
            finishTimestamp = getRuntimeContext().getState(new ValueStateDescriptor<>("finishTimestamp", Long.class));
        }

        @Override
        public void processElement(StageEvent event, Context ctx, Collector<String> out) throws Exception {
            Long tsObj = ctx.timestamp();
            if (tsObj == null) {
                return;
            }
            long ts = tsObj;

            if (event.isSubmit()) {
                Long ft = finishTimestamp.value();
                if (ft != null && ts > ft) {
                    return;
                }

                Long last = lastSubmitTimestamp.value();
                long current = valueOrZero(currentStageCount.value());
                long max = valueOrZero(maxStageCount.value());

                if (last == null) {
                    current = 1;
                } else if (ts - last >= gapMicros) {
                    if (current > max) {
                        max = current;
                    }
                    current = 1;
                } else {
                    current = current + 1;
                }

                lastSubmitTimestamp.update(ts);
                currentStageCount.update(current);
                maxStageCount.update(max);
                return;
            }

            if (event.isFinish()) {
                Long existing = finishTimestamp.value();
                if (existing == null || ts < existing) {
                    if (existing != null) {
                        ctx.timerService().deleteEventTimeTimer(existing);
                    }
                    finishTimestamp.update(ts);
                    ctx.timerService().registerEventTimeTimer(ts);
                }
            }
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<String> out) throws Exception {
            Long ft = finishTimestamp.value();
            if (ft == null || timestamp != ft) {
                return;
            }

            long max = valueOrZero(maxStageCount.value());
            long current = valueOrZero(currentStageCount.value());
            if (current > max) {
                max = current;
            }

            out.collect("(" + ctx.getCurrentKey() + "," + max + ")");

            lastSubmitTimestamp.clear();
            currentStageCount.clear();
            maxStageCount.clear();
            finishTimestamp.clear();
        }

        private static long valueOrZero(Long value) {
            return value == null ? 0L : value;
        }
    }

    private static class TaskEventSource extends RichSourceFunction<TaskEvent> {

        private final String path;
        private volatile boolean running = true;

        private TaskEventSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<TaskEvent> ctx) throws Exception {
            if (path == null) {
                throw new IllegalArgumentException("task_input is required");
            }

            try (BufferedReader reader = new BufferedReader(new InputStreamReader(new GZIPInputStream(new FileInputStream(path)), StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    TaskEvent event = TaskEvent.fromCsv(line);
                    if (event == null) {
                        continue;
                    }
                    synchronized (ctx.getCheckpointLock()) {
                        ctx.collect(event);
                    }
                }
            }
        }

        @Override
        public void cancel() {
            running = false;
        }
    }

    private static class JobEventSource extends RichSourceFunction<JobEvent> {

        private final String path;
        private volatile boolean running = true;

        private JobEventSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<JobEvent> ctx) throws Exception {
            if (path == null) {
                throw new IllegalArgumentException("job_input is required");
            }

            try (BufferedReader reader = new BufferedReader(new InputStreamReader(new GZIPInputStream(new FileInputStream(path)), StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    JobEvent event = JobEvent.fromCsv(line);
                    if (event == null) {
                        continue;
                    }
                    synchronized (ctx.getCheckpointLock()) {
                        ctx.collect(event);
                    }
                }
            }
        }

        @Override
        public void cancel() {
            running = false;
        }
    }

    private static class LocalFileSink extends RichSinkFunction<String> {

        private final String outputPath;
        private transient BufferedWriter writer;

        private LocalFileSink(String outputPath) {
            this.outputPath = outputPath;
        }

        @Override
        public void open(Configuration parameters) throws IOException {
            if (outputPath == null) {
                throw new IllegalArgumentException("output is required");
            }

            Path path = Paths.get(outputPath);
            Path parent = path.getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }

            writer = Files.newBufferedWriter(
                    path,
                    StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE,
                    StandardOpenOption.TRUNCATE_EXISTING,
                    StandardOpenOption.WRITE);
        }

        @Override
        public synchronized void invoke(String value, Context context) throws IOException {
            writer.write(value);
            writer.newLine();
            writer.flush();
        }

        @Override
        public void close() throws IOException {
            if (writer != null) {
                writer.close();
            }
        }
    }
}
