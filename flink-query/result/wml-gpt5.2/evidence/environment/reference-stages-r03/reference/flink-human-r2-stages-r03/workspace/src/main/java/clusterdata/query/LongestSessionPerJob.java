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
import org.apache.flink.streaming.api.datastream.KeyedStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.streaming.api.functions.sink.SinkFunction;
import org.apache.flink.streaming.api.functions.source.SourceFunction;
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

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        final int sesssize = params.getInt("sesssize", 600);
        final long inactivityGapMicros = sesssize * 1_000_000L;

        // set up streaming execution environment
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);

        SourceFunction<TaskEvent> taskSource = taskEvents != null ? taskEvents : new TaskEventCsvSource(taskInput);
        SourceFunction<JobEvent> jobSource = jobEvents != null ? jobEvents : new JobEventCsvSource(jobInput);

        DataStream<TaskEvent> taskStream = env.addSource(taskSource)
                .assignTimestampsAndWatermarks(
                        WatermarkStrategy.<TaskEvent>forMonotonousTimestamps()
                                .withTimestampAssigner((event, previousTimestamp) -> event.timestamp)
                )
                .filter(e -> e.eventType == TaskEvent.EVENT_SUBMIT);

        DataStream<JobEvent> jobStream = env.addSource(jobSource)
                .assignTimestampsAndWatermarks(
                        WatermarkStrategy.<JobEvent>forMonotonousTimestamps()
                                .withTimestampAssigner((event, previousTimestamp) -> event.timestamp)
                )
                .filter(e -> e.eventType == JobEvent.EVENT_FINISH);

        KeyedStream<TaskEvent, Long> keyedTasks = taskStream.keyBy(TaskEvent::getJobId);
        KeyedStream<JobEvent, Long> keyedJobs = jobStream.keyBy(JobEvent::getJobId);

        DataStream<String> results = keyedTasks
                .connect(keyedJobs)
                .process(new LongestStageAfterFinish(inactivityGapMicros));

        SinkFunction<String> sink = out != null ? (SinkFunction<String>) out : new LocalFileSink(outputPath);
        results.addSink(sink).setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    private static final class LongestStageAfterFinish extends KeyedCoProcessFunction<Long, TaskEvent, JobEvent, String> {

        private final long inactivityGapMicros;

        private transient ValueState<Long> lastSubmitTs;
        private transient ValueState<Integer> currentStageCount;
        private transient ValueState<Integer> maxStageCount;

        private transient ValueState<Long> finishTs;
        private transient ValueState<Long> outputTimerTs;

        LongestStageAfterFinish(long inactivityGapMicros) {
            this.inactivityGapMicros = inactivityGapMicros;
        }

        @Override
        public void open(Configuration parameters) {
            lastSubmitTs = getRuntimeContext().getState(new ValueStateDescriptor<>("lastSubmitTs", Long.class));
            currentStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("currentStageCount", Integer.class));
            maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Integer.class));

            finishTs = getRuntimeContext().getState(new ValueStateDescriptor<>("finishTs", Long.class));
            outputTimerTs = getRuntimeContext().getState(new ValueStateDescriptor<>("outputTimerTs", Long.class));
        }

        @Override
        public void processElement1(TaskEvent value, Context ctx, Collector<String> out) throws Exception {
            long ts = value.timestamp;

            Long lastTs = lastSubmitTs.value();
            Integer stageCount = currentStageCount.value();
            if (stageCount == null) {
                stageCount = 0;
            }

            if (lastTs == null || stageCount == 0) {
                stageCount = 1;
            } else {
                long delta = ts - lastTs;
                if (delta > inactivityGapMicros) {
                    Integer maxCount = maxStageCount.value();
                    if (maxCount == null) {
                        maxCount = 0;
                    }
                    if (stageCount > maxCount) {
                        maxStageCount.update(stageCount);
                    }
                    stageCount = 1;
                } else {
                    stageCount = stageCount + 1;
                }
            }

            lastSubmitTs.update(ts);
            currentStageCount.update(stageCount);

            Long ft = finishTs.value();
            if (ft != null && ts > ft) {
                scheduleOrRescheduleOutputTimer(ctx, ts);
            }
        }

        @Override
        public void processElement2(JobEvent value, Context ctx, Collector<String> out) throws Exception {
            long ts = value.timestamp;

            Long currentFinish = finishTs.value();
            if (currentFinish == null || ts > currentFinish) {
                finishTs.update(ts);
                scheduleOrRescheduleOutputTimer(ctx, ts);
            } else if (outputTimerTs.value() == null) {
                scheduleOrRescheduleOutputTimer(ctx, currentFinish);
            }
        }

        private void scheduleOrRescheduleOutputTimer(Context ctx, long candidateTs) throws Exception {
            Long currentTimer = outputTimerTs.value();
            if (currentTimer == null || candidateTs > currentTimer) {
                if (currentTimer != null) {
                    ctx.timerService().deleteEventTimeTimer(currentTimer);
                }
                ctx.timerService().registerEventTimeTimer(candidateTs);
                outputTimerTs.update(candidateTs);
            }
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<String> out) throws Exception {
            Long expected = outputTimerTs.value();
            if (expected == null || expected != timestamp) {
                return;
            }

            Integer maxCount = maxStageCount.value();
            if (maxCount == null) {
                maxCount = 0;
            }

            Integer stageCount = currentStageCount.value();
            if (stageCount != null && stageCount > maxCount) {
                maxCount = stageCount;
            }

            if (maxCount > 0) {
                out.collect("(" + ctx.getCurrentKey() + "," + maxCount + ")");
            }

            lastSubmitTs.clear();
            currentStageCount.clear();
            maxStageCount.clear();
            finishTs.clear();
            outputTimerTs.clear();
        }
    }

    private static final class TaskEventCsvSource implements SourceFunction<TaskEvent> {

        private final String inputPath;
        private volatile boolean running = true;

        private TaskEventCsvSource(String inputPath) {
            this.inputPath = inputPath;
        }

        @Override
        public void run(SourceContext<TaskEvent> ctx) throws Exception {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(openInputStream(inputPath), StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }
                    try {
                        ctx.collect(TaskEvent.fromCsvLine(line));
                    } catch (RuntimeException ignored) {
                        // Skip malformed lines.
                    }
                }
            }
        }

        @Override
        public void cancel() {
            running = false;
        }
    }

    private static final class JobEventCsvSource implements SourceFunction<JobEvent> {

        private final String inputPath;
        private volatile boolean running = true;

        private JobEventCsvSource(String inputPath) {
            this.inputPath = inputPath;
        }

        @Override
        public void run(SourceContext<JobEvent> ctx) throws Exception {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(openInputStream(inputPath), StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }
                    try {
                        ctx.collect(JobEvent.fromCsvLine(line));
                    } catch (RuntimeException ignored) {
                        // Skip malformed lines.
                    }
                }
            }
        }

        @Override
        public void cancel() {
            running = false;
        }
    }

    private static InputStream openInputStream(String inputPath) throws Exception {
        if (inputPath == null) {
            throw new IllegalArgumentException("Missing input path");
        }
        InputStream in = Files.newInputStream(Paths.get(inputPath));
        if (inputPath.endsWith(".gz")) {
            return new GZIPInputStream(in);
        }
        return in;
    }

    private static final class LocalFileSink extends RichSinkFunction<String> {

        private final String outputPath;
        private transient BufferedWriter writer;

        private LocalFileSink(String outputPath) {
            this.outputPath = outputPath;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            if (outputPath == null) {
                throw new IllegalArgumentException("Missing output path");
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
}
