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
import org.apache.flink.streaming.api.datastream.ConnectedStreams;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.streaming.api.functions.source.SourceFunction;
import org.apache.flink.streaming.api.functions.sink.SinkFunction;
import org.apache.flink.util.Collector;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.zip.GZIPInputStream;

public class LongestSessionPerJob extends AppBase {

    private static final int TASK_EVENT_TYPE_SUBMIT = 0;
    private static final int JOB_EVENT_TYPE_FINISH = 4;
    private static final int JOB_EVENT_TYPE_KILL = 5;

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        final int sesssize = params.getInt("sesssize", 600);

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);

        DataStream<TaskEvent> taskEventsStream = env.addSource(taskSourceOrTest(new TaskEventSource(taskInput)));
        DataStream<JobEvent> jobEventsStream = env.addSource(jobSourceOrTest(new JobEventSource(jobInput)));

        WatermarkStrategy<TaskEvent> taskWm = WatermarkStrategy
                .<TaskEvent>forMonotonousTimestamps()
                .withTimestampAssigner((e, ts) -> e.getTimestampMs());

        WatermarkStrategy<JobEvent> jobWm = WatermarkStrategy
                .<JobEvent>forMonotonousTimestamps()
                .withTimestampAssigner((e, ts) -> e.getTimestampMs());

        DataStream<TaskEvent> submits = taskEventsStream
                .filter(e -> e.eventType == TASK_EVENT_TYPE_SUBMIT)
                .assignTimestampsAndWatermarks(taskWm);

        DataStream<JobEvent> jobEnds = jobEventsStream
                .filter(e -> e.eventType == JOB_EVENT_TYPE_FINISH || e.eventType == JOB_EVENT_TYPE_KILL)
                .assignTimestampsAndWatermarks(jobWm);

        ConnectedStreams<TaskEvent, JobEvent> connected = submits
                .connect(jobEnds)
                .keyBy(e -> e.jobId, e -> e.jobId);

        long gapMs = sesssize * 1000L;
        DataStream<Tuple2<Long, Long>> longestStage = connected.process(new LongestStagePerJobProcess(gapMs));

        @SuppressWarnings("unchecked")
        SinkFunction<Tuple2<Long, Long>> sink = (SinkFunction<Tuple2<Long, Long>>) sinkOrTest(new LineFileSink(outputPath));

        longestStage
                .addSink(sink)
                .setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    public static final class TaskEventSource implements SourceFunction<TaskEvent> {
        private final String path;
        private volatile boolean running = true;

        public TaskEventSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<TaskEvent> ctx) throws Exception {
            if (path == null) {
                throw new IllegalArgumentException("task_input is required");
            }

            try (BufferedReader reader = new BufferedReader(new InputStreamReader(open(path), StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    String[] p = line.split(",", -1);
                    if (p.length < 6 || p[0].isEmpty() || p[2].isEmpty() || p[5].isEmpty()) {
                        continue;
                    }

                    long timestamp = Long.parseLong(p[0]);
                    long jobId = Long.parseLong(p[2]);
                    int eventType = Integer.parseInt(p[5]);
                    ctx.collect(new TaskEvent(timestamp, jobId, eventType));
                }
            }
        }

        @Override
        public void cancel() {
            running = false;
        }
    }

    public static final class JobEventSource implements SourceFunction<JobEvent> {
        private final String path;
        private volatile boolean running = true;

        public JobEventSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<JobEvent> ctx) throws Exception {
            if (path == null) {
                throw new IllegalArgumentException("job_input is required");
            }

            try (BufferedReader reader = new BufferedReader(new InputStreamReader(open(path), StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    String[] p = line.split(",", -1);
                    if (p.length < 4 || p[0].isEmpty() || p[2].isEmpty() || p[3].isEmpty()) {
                        continue;
                    }

                    long timestamp = Long.parseLong(p[0]);
                    long jobId = Long.parseLong(p[2]);
                    int eventType = Integer.parseInt(p[3]);
                    ctx.collect(new JobEvent(timestamp, jobId, eventType));
                }
            }
        }

        @Override
        public void cancel() {
            running = false;
        }
    }

    private static InputStream open(String path) throws IOException {
        InputStream in = new FileInputStream(path);
        if (path.endsWith(".gz")) {
            return new GZIPInputStream(in);
        }
        return in;
    }

    public static final class LongestStagePerJobProcess extends KeyedCoProcessFunction<Long, TaskEvent, JobEvent, Tuple2<Long, Long>> {
        private final long gapMs;

        private transient ValueState<Long> lastSubmitTsMs;
        private transient ValueState<Long> currentStageCount;
        private transient ValueState<Long> maxStageCount;
        private transient ValueState<Long> finishTsMs;
        private transient ValueState<Boolean> emitted;

        public LongestStagePerJobProcess(long gapMs) {
            this.gapMs = gapMs;
        }

        @Override
        public void open(Configuration parameters) {
            lastSubmitTsMs = getRuntimeContext().getState(new ValueStateDescriptor<>("lastSubmitTsMs", Long.class));
            currentStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("currentStageCount", Long.class));
            maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Long.class));
            finishTsMs = getRuntimeContext().getState(new ValueStateDescriptor<>("finishTsMs", Long.class));
            emitted = getRuntimeContext().getState(new ValueStateDescriptor<>("emitted", Boolean.class));
        }

        @Override
        public void processElement1(TaskEvent value, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            if (Boolean.TRUE.equals(emitted.value())) {
                return;
            }

            long tsMs = value.getTimestampMs();
            Long lastTs = lastSubmitTsMs.value();
            long cur = defaultLong(currentStageCount.value());
            long max = defaultLong(maxStageCount.value());

            if (lastTs != null && tsMs - lastTs >= gapMs) {
                max = Math.max(max, cur);
                cur = 0L;
            }

            cur += 1L;

            lastSubmitTsMs.update(tsMs);
            currentStageCount.update(cur);
            maxStageCount.update(max);
        }

        @Override
        public void processElement2(JobEvent value, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            if (Boolean.TRUE.equals(emitted.value())) {
                return;
            }

            long tsMs = value.getTimestampMs();
            finishTsMs.update(tsMs);
            ctx.timerService().registerEventTimeTimer(tsMs);
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            if (Boolean.TRUE.equals(emitted.value())) {
                return;
            }

            Long finish = finishTsMs.value();
            if (finish == null || finish != timestamp) {
                return;
            }

            long cur = defaultLong(currentStageCount.value());
            long max = Math.max(defaultLong(maxStageCount.value()), cur);
            out.collect(Tuple2.of(ctx.getCurrentKey(), max));

            emitted.update(true);
            lastSubmitTsMs.clear();
            currentStageCount.clear();
            maxStageCount.clear();
            finishTsMs.clear();
        }

        private static long defaultLong(Long v) {
            return v == null ? 0L : v;
        }
    }

    public static final class LineFileSink extends RichSinkFunction<Tuple2<Long, Long>> {
        private final String path;
        private transient BufferedWriter writer;

        public LineFileSink(String path) {
            this.path = path;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            if (path == null) {
                throw new IllegalArgumentException("output is required");
            }

            File out = new File(path);
            File parent = out.getParentFile();
            if (parent != null) {
                parent.mkdirs();
            }
            writer = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(out, false), StandardCharsets.UTF_8));
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
