package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.streaming.api.functions.source.RichSourceFunction;
import org.apache.flink.util.Collector;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.zip.GZIPInputStream;

public class LongestSessionPerJob extends AppBase {

    private static final long END_OF_STREAM_TIMER = Long.MAX_VALUE - 1;

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        System.out.println("task_input  " + taskInput);
        System.out.println("job_input  " + jobInput);
        final int sesssize = params.getInt("sesssize", 600);

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        DataStream<TaskEvent> tasks = env
                .addSource(taskSourceOrTest(new TaskEventCsvSource(taskInput)))
                .assignTimestampsAndWatermarks(
                        WatermarkStrategy.<TaskEvent>forMonotonousTimestamps()
                                .withTimestampAssigner((e, ts) -> e.timestampMs)
                );

        DataStream<JobEvent> jobs = env
                .addSource(jobSourceOrTest(new JobEventCsvSource(jobInput)))
                .assignTimestampsAndWatermarks(
                        WatermarkStrategy.<JobEvent>forMonotonousTimestamps()
                                .withTimestampAssigner((e, ts) -> e.timestampMs)
                );

        DataStream<TaskEvent> submitTasks = tasks.filter(e -> e.eventType == TaskEvent.EVENT_SUBMIT);
        DataStream<JobEvent> terminalJobs = jobs.filter(JobEvent::isTerminal);

        DataStream<Tuple2<Long, Long>> longestStagePerJob = submitTasks
                .connect(terminalJobs)
                .keyBy(t -> t.jobId, j -> j.jobId)
                .process(new LongestStagePerJob(sesssize));

        DataStream<String> formatted = longestStagePerJob.map(t -> "(" + t.f0 + "," + t.f1 + ")");
        formatted
                .addSink((org.apache.flink.streaming.api.functions.sink.SinkFunction<String>) sinkOrTest(new LocalFileSink(outputPath)))
                .setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    private static final class TaskEventCsvSource extends RichSourceFunction<TaskEvent> {

        private final String inputPath;
        private transient volatile boolean running;

        private TaskEventCsvSource(String inputPath) {
            this.inputPath = inputPath;
            this.running = true;
        }

        @Override
        public void run(SourceContext<TaskEvent> ctx) throws Exception {
            try (InputStream raw = Files.newInputStream(Paths.get(inputPath));
                 InputStream in = inputPath.endsWith(".gz") ? new GZIPInputStream(raw) : raw;
                 BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {

                String line;
                while (running && (line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }
                    TaskEvent event = TaskEvent.fromCsvLine(line);
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

    private static final class JobEventCsvSource extends RichSourceFunction<JobEvent> {

        private final String inputPath;
        private transient volatile boolean running;

        private JobEventCsvSource(String inputPath) {
            this.inputPath = inputPath;
            this.running = true;
        }

        @Override
        public void run(SourceContext<JobEvent> ctx) throws Exception {
            try (InputStream raw = Files.newInputStream(Paths.get(inputPath));
                 InputStream in = inputPath.endsWith(".gz") ? new GZIPInputStream(raw) : raw;
                 BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {

                String line;
                while (running && (line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }
                    JobEvent event = JobEvent.fromCsvLine(line);
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

    private static final class LocalFileSink extends RichSinkFunction<String> {

        private final String outputPath;
        private transient BufferedWriter writer;

        private LocalFileSink(String outputPath) {
            this.outputPath = outputPath;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
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
                    StandardOpenOption.WRITE
            );
        }

        @Override
        public void invoke(String value, Context context) throws Exception {
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

    private static final class LongestStagePerJob extends KeyedCoProcessFunction<Long, TaskEvent, JobEvent, Tuple2<Long, Long>> {

        private final long gapMs;

        private transient ValueState<Long> currentStageCount;
        private transient ValueState<Long> lastSubmitTs;
        private transient ValueState<Long> maxStageCount;
        private transient ValueState<Long> jobEndTs;
        private transient ValueState<Boolean> emitted;

        private LongestStagePerJob(int gapSeconds) {
            this.gapMs = gapSeconds * 1000L;
        }

        @Override
        public void open(Configuration parameters) {
            currentStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("currentStageCount", Long.class));
            lastSubmitTs = getRuntimeContext().getState(new ValueStateDescriptor<>("lastSubmitTs", Long.class));
            maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Long.class));
            jobEndTs = getRuntimeContext().getState(new ValueStateDescriptor<>("jobEndTs", Long.class));
            emitted = getRuntimeContext().getState(new ValueStateDescriptor<>("emitted", Boolean.class));
        }

        @Override
        public void processElement1(TaskEvent value, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            if (Boolean.TRUE.equals(emitted.value())) {
                return;
            }
            registerEndOfStreamTimer(ctx);

            Long stageCount = currentStageCount.value();
            Long lastTs = lastSubmitTs.value();
            if (stageCount == null) {
                stageCount = 0L;
            }

            if (lastTs == null) {
                stageCount = 1L;
            } else if (value.timestampMs - lastTs >= gapMs) {
                Long max = maxStageCount.value();
                if (max == null) {
                    max = 0L;
                }
                if (stageCount > max) {
                    max = stageCount;
                }
                maxStageCount.update(max);
                stageCount = 1L;
            } else {
                stageCount = stageCount + 1L;
            }

            currentStageCount.update(stageCount);
            lastSubmitTs.update(value.timestampMs);
        }

        @Override
        public void processElement2(JobEvent value, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            if (Boolean.TRUE.equals(emitted.value())) {
                return;
            }
            registerEndOfStreamTimer(ctx);

            jobEndTs.update(value.timestampMs);
            ctx.timerService().registerEventTimeTimer(value.timestampMs);
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            if (Boolean.TRUE.equals(emitted.value())) {
                return;
            }

            Long endTs = jobEndTs.value();
            if (endTs != null && endTs == timestamp) {
                emitAndClear(ctx.getCurrentKey(), out);
                return;
            }

            if (timestamp == END_OF_STREAM_TIMER) {
                emitAndClear(ctx.getCurrentKey(), out);
            }
        }

        private void registerEndOfStreamTimer(Context ctx) {
            ctx.timerService().registerEventTimeTimer(END_OF_STREAM_TIMER);
        }

        private void emitAndClear(long jobId, Collector<Tuple2<Long, Long>> out) throws Exception {
            Long max = maxStageCount.value();
            if (max == null) {
                max = 0L;
            }

            Long stageCount = currentStageCount.value();
            if (stageCount != null && stageCount > max) {
                max = stageCount;
            }

            out.collect(Tuple2.of(jobId, max));

            emitted.update(true);
            currentStageCount.clear();
            lastSubmitTs.clear();
            maxStageCount.clear();
            jobEndTs.clear();
        }
    }
}
