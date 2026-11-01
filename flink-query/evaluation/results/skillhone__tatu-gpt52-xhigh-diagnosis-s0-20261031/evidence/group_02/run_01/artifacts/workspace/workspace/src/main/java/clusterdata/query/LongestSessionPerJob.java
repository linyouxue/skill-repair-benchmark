package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import org.apache.flink.api.common.eventtime.SerializableTimestampAssigner;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.datastream.ConnectedStreams;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.streaming.api.functions.source.RichSourceFunction;
import org.apache.flink.streaming.api.functions.source.SourceFunction;
import org.apache.flink.streaming.api.functions.sink.SinkFunction;
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
import java.time.Duration;
import java.util.zip.GZIPInputStream;

public class LongestSessionPerJob extends AppBase {

    private static final int TASK_EVENT_SUBMIT = 0;
    private static final int JOB_EVENT_FINISH = 4;
    private static final int JOB_EVENT_KILL = 5;

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        System.out.println("task_input  " + taskInput);
        System.out.println("job_input  " + jobInput);
        final int sesssize = params.getInt("sesssize", 600);

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);

        SourceFunction<TaskEvent> taskSource = taskSourceOrTest(new TaskEventSource(taskInput));
        SourceFunction<JobEvent> jobSource = jobSourceOrTest(new JobEventSource(jobInput));

        WatermarkStrategy<TaskEvent> taskWm = WatermarkStrategy
                .<TaskEvent>forBoundedOutOfOrderness(Duration.ZERO)
                .withTimestampAssigner((SerializableTimestampAssigner<TaskEvent>) (e, ts) -> e.timestampMs);

        WatermarkStrategy<JobEvent> jobWm = WatermarkStrategy
                .<JobEvent>forBoundedOutOfOrderness(Duration.ZERO)
                .withTimestampAssigner((SerializableTimestampAssigner<JobEvent>) (e, ts) -> e.timestampMs);

        DataStream<TaskEvent> submits = env
                .addSource(taskSource)
                .filter(e -> e != null && e.eventType == TASK_EVENT_SUBMIT)
                .assignTimestampsAndWatermarks(taskWm);

        DataStream<JobEvent> jobEnds = env
                .addSource(jobSource)
                .filter(e -> e != null && (e.eventType == JOB_EVENT_FINISH || e.eventType == JOB_EVENT_KILL))
                .assignTimestampsAndWatermarks(jobWm);

        ConnectedStreams<TaskEvent, JobEvent> connected = submits.connect(jobEnds).keyBy(t -> t.jobId, j -> j.jobId);

        DataStream<Tuple2<Long, Long>> result = connected.process(new LongestStageWhenJobEnds(sesssize));

        @SuppressWarnings("unchecked")
        SinkFunction<Tuple2<Long, Long>> sink =
                (SinkFunction<Tuple2<Long, Long>>) sinkOrTest(new TextFileSink(outputPath));
        result.addSink(sink);

        env.execute("LongestSessionPerJob");
    }

    private static class TaskEventSource extends RichSourceFunction<TaskEvent> {
        private final String path;
        private volatile boolean running = true;

        private TaskEventSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<TaskEvent> ctx) throws Exception {
            if (path == null || path.isBlank()) {
                return;
            }

            Path p = Paths.get(path);
            try (InputStream raw = Files.newInputStream(p);
                 InputStream in = path.endsWith(".gz") ? new GZIPInputStream(raw) : raw;
                 BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {

                String line;
                while (running && (line = reader.readLine()) != null) {
                    TaskEvent event;
                    try {
                        event = TaskEvent.fromCsvLine(line);
                    } catch (Exception ignored) {
                        continue;
                    }

                    if (event != null) {
                        synchronized (ctx.getCheckpointLock()) {
                            ctx.collect(event);
                        }
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
            if (path == null || path.isBlank()) {
                return;
            }

            Path p = Paths.get(path);
            try (InputStream raw = Files.newInputStream(p);
                 InputStream in = path.endsWith(".gz") ? new GZIPInputStream(raw) : raw;
                 BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {

                String line;
                while (running && (line = reader.readLine()) != null) {
                    JobEvent event;
                    try {
                        event = JobEvent.fromCsvLine(line);
                    } catch (Exception ignored) {
                        continue;
                    }

                    if (event != null) {
                        synchronized (ctx.getCheckpointLock()) {
                            ctx.collect(event);
                        }
                    }
                }
            }
        }

        @Override
        public void cancel() {
            running = false;
        }
    }

    private static class LongestStageWhenJobEnds extends KeyedCoProcessFunction<Long, TaskEvent, JobEvent, Tuple2<Long, Long>> {
        private final long gapMs;

        private transient ValueState<Long> lastSubmitTsMs;
        private transient ValueState<Long> currentSessionCount;
        private transient ValueState<Long> maxSessionCount;
        private transient ValueState<Long> endTsMs;

        private LongestStageWhenJobEnds(int gapSeconds) {
            this.gapMs = gapSeconds * 1000L;
        }

        @Override
        public void open(Configuration parameters) {
            lastSubmitTsMs = getRuntimeContext().getState(new ValueStateDescriptor<>("lastSubmitTsMs", Long.class));
            currentSessionCount = getRuntimeContext().getState(new ValueStateDescriptor<>("currentSessionCount", Long.class));
            maxSessionCount = getRuntimeContext().getState(new ValueStateDescriptor<>("maxSessionCount", Long.class));
            endTsMs = getRuntimeContext().getState(new ValueStateDescriptor<>("endTsMs", Long.class));
        }

        @Override
        public void processElement1(TaskEvent event, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            long ts = event.timestampMs;

            Long lastTs = lastSubmitTsMs.value();
            Long curr = currentSessionCount.value();
            Long max = maxSessionCount.value();
            if (curr == null) {
                curr = 0L;
            }
            if (max == null) {
                max = 0L;
            }

            if (lastTs != null && ts - lastTs > gapMs) {
                if (curr > max) {
                    max = curr;
                }
                curr = 0L;
            }

            curr += 1L;
            lastSubmitTsMs.update(ts);
            currentSessionCount.update(curr);
            maxSessionCount.update(max);
        }

        @Override
        public void processElement2(JobEvent event, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            Long existingEndTs = endTsMs.value();
            if (existingEndTs != null) {
                return;
            }

            long endTime = event.timestampMs;
            endTsMs.update(endTime);
            ctx.timerService().registerEventTimeTimer(endTime);
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            Long expected = endTsMs.value();
            if (expected == null || expected != timestamp) {
                return;
            }

            Long curr = currentSessionCount.value();
            Long max = maxSessionCount.value();

            long best = 0L;
            if (curr != null && curr > best) {
                best = curr;
            }
            if (max != null && max > best) {
                best = max;
            }

            out.collect(Tuple2.of(ctx.getCurrentKey(), best));

            lastSubmitTsMs.clear();
            currentSessionCount.clear();
            maxSessionCount.clear();
            endTsMs.clear();
        }
    }

    private static class TextFileSink extends RichSinkFunction<Tuple2<Long, Long>> {
        private final String outputPath;
        private transient BufferedWriter writer;

        private TextFileSink(String outputPath) {
            this.outputPath = outputPath;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            if (outputPath == null || outputPath.isBlank()) {
                throw new IllegalArgumentException("Parameter 'output' is required");
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
                    StandardOpenOption.TRUNCATE_EXISTING);
        }

        @Override
        public void invoke(Tuple2<Long, Long> value, Context context) throws Exception {
            writer.write(value.toString());
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
