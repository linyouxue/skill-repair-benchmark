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
import org.apache.flink.streaming.api.functions.sink.SinkFunction;
import org.apache.flink.streaming.api.functions.source.RichSourceFunction;
import org.apache.flink.util.Collector;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.GZIPInputStream;

public class LongestSessionPerJob extends AppBase {

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        final long sessionGapSeconds = params.getInt("sesssize", 600);

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);

        DataStream<TaskEvent> tasks =
                env.addSource(taskSourceOrTest(new TaskEventSource(taskInput))).name("task-events");
        DataStream<JobEvent> jobs =
                env.addSource(jobSourceOrTest(new JobEventSource(jobInput))).name("job-events");

        WatermarkStrategy<TaskEvent> taskWm =
                WatermarkStrategy.<TaskEvent>forMonotonousTimestamps()
                        .withTimestampAssigner((e, ts) -> e.timestamp);
        WatermarkStrategy<JobEvent> jobWm =
                WatermarkStrategy.<JobEvent>forMonotonousTimestamps()
                        .withTimestampAssigner((e, ts) -> e.timestamp);

        DataStream<TaskEvent> submits =
                tasks.assignTimestampsAndWatermarks(taskWm)
                        .filter(TaskEvent::isSubmit)
                        .name("task-submits");
        DataStream<JobEvent> terminalJobs =
                jobs.assignTimestampsAndWatermarks(jobWm)
                        .filter(JobEvent::isTerminal)
                        .name("job-terminal");

        DataStream<Tuple2<Long, Long>> result =
                submits.keyBy(TaskEvent::getJobId)
                        .connect(terminalJobs.keyBy(JobEvent::getJobId))
                        .process(new LongestStagePerJobOnFinish(sessionGapSeconds * 1000L))
                        .name("longest-stage-per-job");

        DataStream<String> formatted =
                result.map(t -> "(" + t.f0 + "," + t.f1 + ")").name("format-output");

        @SuppressWarnings("unchecked")
        SinkFunction<String> sink = (SinkFunction<String>) sinkOrTest(new SingleFileSink(outputPath));
        formatted.addSink(sink).name("output").setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    private static final class TaskEventSource extends RichSourceFunction<TaskEvent> {
        private final String path;
        private volatile boolean running = true;

        private TaskEventSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<TaskEvent> ctx) throws Exception {
            if (path == null) {
                return;
            }

            try (InputStream in = openPossiblyGzipped(path);
                    BufferedReader reader =
                            new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }
                    ctx.collect(TaskEvent.fromCsvLine(line));
                }
            }
        }

        @Override
        public void cancel() {
            running = false;
        }
    }

    private static final class JobEventSource extends RichSourceFunction<JobEvent> {
        private final String path;
        private volatile boolean running = true;

        private JobEventSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<JobEvent> ctx) throws Exception {
            if (path == null) {
                return;
            }

            try (InputStream in = openPossiblyGzipped(path);
                    BufferedReader reader =
                            new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }
                    ctx.collect(JobEvent.fromCsvLine(line));
                }
            }
        }

        @Override
        public void cancel() {
            running = false;
        }
    }

    private static InputStream openPossiblyGzipped(String path) throws Exception {
        InputStream raw = Files.newInputStream(Path.of(path));
        if (path.endsWith(".gz")) {
            return new GZIPInputStream(raw);
        }
        return raw;
    }

    private static final class SingleFileSink extends RichSinkFunction<String> {
        private final String outputPath;

        private transient java.io.BufferedWriter writer;

        private SingleFileSink(String outputPath) {
            this.outputPath = outputPath;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            if (outputPath == null) {
                return;
            }

            Path p = Path.of(outputPath);
            Path parent = p.getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }

            writer = Files.newBufferedWriter(p, StandardCharsets.UTF_8);
        }

        @Override
        public void invoke(String value, Context context) throws Exception {
            if (writer == null) {
                return;
            }

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

    private static final class LongestStagePerJobOnFinish
            extends KeyedCoProcessFunction<Long, TaskEvent, JobEvent, Tuple2<Long, Long>> {
        private final long sessionGapMillis;

        private transient ValueState<Long> lastSubmitTs;
        private transient ValueState<Long> currentStageCount;
        private transient ValueState<Long> maxStageCount;
        private transient ValueState<Long> jobEndTs;
        private transient ValueState<Boolean> emitted;

        private LongestStagePerJobOnFinish(long sessionGapMillis) {
            this.sessionGapMillis = sessionGapMillis;
        }

        @Override
        public void open(Configuration parameters) {
            lastSubmitTs =
                    getRuntimeContext().getState(new ValueStateDescriptor<>("lastSubmitTs", Long.class));
            currentStageCount =
                    getRuntimeContext()
                            .getState(new ValueStateDescriptor<>("currentStageCount", Long.class));
            maxStageCount =
                    getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Long.class));
            jobEndTs = getRuntimeContext().getState(new ValueStateDescriptor<>("jobEndTs", Long.class));
            emitted = getRuntimeContext().getState(new ValueStateDescriptor<>("emitted", Boolean.class));
        }

        @Override
        public void processElement1(TaskEvent value, Context ctx, Collector<Tuple2<Long, Long>> out)
                throws Exception {
            if (Boolean.TRUE.equals(emitted.value())) {
                return;
            }

            Long endTs = jobEndTs.value();
            long ts = value.timestamp;
            if (endTs != null && ts > endTs) {
                return;
            }

            Long last = lastSubmitTs.value();
            long stageCount = currentStageCount.value() == null ? 0L : currentStageCount.value();
            long max = maxStageCount.value() == null ? 0L : maxStageCount.value();

            if (last == null) {
                stageCount = 1L;
            } else if (ts - last < sessionGapMillis) {
                stageCount += 1L;
            } else {
                if (stageCount > max) {
                    max = stageCount;
                }
                stageCount = 1L;
            }

            lastSubmitTs.update(ts);
            currentStageCount.update(stageCount);
            maxStageCount.update(max);
        }

        @Override
        public void processElement2(JobEvent value, Context ctx, Collector<Tuple2<Long, Long>> out)
                throws Exception {
            if (Boolean.TRUE.equals(emitted.value())) {
                return;
            }

            Long existingEnd = jobEndTs.value();
            long ts = value.timestamp;
            if (existingEnd == null || ts < existingEnd) {
                jobEndTs.update(ts);
                ctx.timerService().registerEventTimeTimer(ts);
            }
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Long>> out)
                throws Exception {
            if (Boolean.TRUE.equals(emitted.value())) {
                return;
            }

            Long endTs = jobEndTs.value();
            if (endTs == null || timestamp != endTs) {
                return;
            }

            long stageCount = currentStageCount.value() == null ? 0L : currentStageCount.value();
            long max = maxStageCount.value() == null ? 0L : maxStageCount.value();
            if (stageCount > max) {
                max = stageCount;
            }

            out.collect(Tuple2.of(ctx.getCurrentKey(), max));
            emitted.update(true);

            lastSubmitTs.clear();
            currentStageCount.clear();
            maxStageCount.clear();
            jobEndTs.clear();
        }
    }
}
