package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
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
import org.apache.flink.streaming.api.functions.source.SourceFunction;
import org.apache.flink.streaming.api.watermark.Watermark;
import org.apache.flink.util.Collector;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileWriter;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.zip.GZIPInputStream;

public class LongestSessionPerJob extends AppBase {

    private static final long MICROS_PER_SECOND = 1_000_000L;

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        System.out.println("task_input  " + taskInput);
        System.out.println("job_input  " + jobInput);
        final int sesssize = params.getInt("sesssize", 600);

        if (taskInput == null || jobInput == null || outputPath == null) {
            throw new IllegalArgumentException("Required parameters: --task_input, --job_input, --output");
        }

        final long sessionGapMicros = sesssize * MICROS_PER_SECOND;

        // set up streaming execution environment
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);

        DataStream<TaskEvent> taskStream =
                env.addSource(taskSourceOrTest(new GzipTaskEventSource(taskInput)))
                        .name("task-events");

        DataStream<JobEvent> jobStream =
                env.addSource(jobSourceOrTest(new GzipJobEventSource(jobInput)))
                        .name("job-events");

        DataStream<TaskEvent> submitTasks = taskStream.filter(TaskEvent::isSubmit).name("task-submit");
        DataStream<JobEvent> finishJobs = jobStream.filter(JobEvent::isFinish).name("job-finish");

        DataStream<Tuple2<Long, Integer>> longestStage =
                submitTasks
                        .connect(finishJobs)
                        .keyBy(TaskEvent::getJobId, JobEvent::getJobId)
                        .process(new LongestStageAfterFinish(sessionGapMicros))
                        .name("longest-stage");

        DataStream<String> formatted = longestStage.map(t -> "(" + t.f0 + "," + t.f1 + ")").name("format");

        formatted
                .addSink((SinkFunction<String>) sinkOrTest(new LocalTextFileSink(outputPath)))
                .name("output")
                .setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    public static final class LongestStageAfterFinish
            extends KeyedCoProcessFunction<Long, TaskEvent, JobEvent, Tuple2<Long, Integer>> {

        private final long sessionGapMicros;

        private transient ValueState<Long> lastSubmitTs;
        private transient ValueState<Integer> currentStageCount;
        private transient ValueState<Integer> maxStageCount;
        private transient ValueState<Long> finishTs;
        private transient ValueState<Boolean> done;

        public LongestStageAfterFinish(long sessionGapMicros) {
            this.sessionGapMicros = sessionGapMicros;
        }

        @Override
        public void open(Configuration parameters) {
            lastSubmitTs =
                    getRuntimeContext().getState(new ValueStateDescriptor<>("lastSubmitTs", Long.class));
            currentStageCount =
                    getRuntimeContext()
                            .getState(new ValueStateDescriptor<>("currentStageCount", Integer.class));
            maxStageCount =
                    getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Integer.class));
            finishTs = getRuntimeContext().getState(new ValueStateDescriptor<>("finishTs", Long.class));
            done = getRuntimeContext().getState(new ValueStateDescriptor<>("done", Boolean.class));
        }

        @Override
        public void processElement1(TaskEvent value, Context ctx, Collector<Tuple2<Long, Integer>> out)
                throws Exception {
            if (Boolean.TRUE.equals(done.value())) {
                return;
            }

            long ts = value.timestamp;

            Long lastTs = lastSubmitTs.value();
            Integer cur = currentStageCount.value();

            if (lastTs == null || ts - lastTs > sessionGapMicros) {
                cur = 1;
            } else {
                cur = (cur == null ? 0 : cur) + 1;
            }

            currentStageCount.update(cur);

            Integer max = maxStageCount.value();
            int newMax = Math.max(max == null ? 0 : max, cur);
            maxStageCount.update(newMax);

            lastSubmitTs.update(ts);
        }

        @Override
        public void processElement2(JobEvent value, Context ctx, Collector<Tuple2<Long, Integer>> out)
                throws Exception {
            if (Boolean.TRUE.equals(done.value())) {
                return;
            }

            long ts = value.timestamp;
            Long existing = finishTs.value();
            if (existing == null || ts < existing) {
                finishTs.update(ts);
                ctx.timerService().registerEventTimeTimer(ts);
            }
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Integer>> out)
                throws Exception {
            if (Boolean.TRUE.equals(done.value())) {
                return;
            }

            Long ft = finishTs.value();
            if (ft == null || timestamp != ft) {
                return;
            }

            Integer max = maxStageCount.value();
            if (max != null && max > 0) {
                out.collect(Tuple2.of(ctx.getCurrentKey(), max));
            }

            done.update(true);
            lastSubmitTs.clear();
            currentStageCount.clear();
            maxStageCount.clear();
            finishTs.clear();
        }
    }

    private abstract static class GzipCsvSource<T> implements SourceFunction<T> {
        private final String path;
        private volatile boolean running = true;

        protected GzipCsvSource(String path) {
            this.path = path;
        }

        protected abstract T parse(String line);

        protected abstract long timestamp(T event);

        @Override
        public void run(SourceContext<T> ctx) throws Exception {
            final Object lock = ctx.getCheckpointLock();

            try (FileInputStream fis = new FileInputStream(path);
                    GZIPInputStream gis = new GZIPInputStream(fis);
                    InputStreamReader isr = new InputStreamReader(gis, StandardCharsets.UTF_8);
                    BufferedReader reader = new BufferedReader(isr)) {

                String line;
                while (running && (line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }

                    T event = parse(line);
                    long ts = timestamp(event);

                    synchronized (lock) {
                        ctx.collectWithTimestamp(event, ts);
                        ctx.emitWatermark(new Watermark(ts - 1));
                    }
                }

                synchronized (lock) {
                    ctx.emitWatermark(Watermark.MAX_WATERMARK);
                }
            }
        }

        @Override
        public void cancel() {
            running = false;
        }
    }

    private static final class GzipTaskEventSource extends GzipCsvSource<TaskEvent> {
        private GzipTaskEventSource(String path) {
            super(path);
        }

        @Override
        protected TaskEvent parse(String line) {
            return TaskEvent.fromCsvLine(line);
        }

        @Override
        protected long timestamp(TaskEvent event) {
            return event.timestamp;
        }
    }

    private static final class GzipJobEventSource extends GzipCsvSource<JobEvent> {
        private GzipJobEventSource(String path) {
            super(path);
        }

        @Override
        protected JobEvent parse(String line) {
            return JobEvent.fromCsvLine(line);
        }

        @Override
        protected long timestamp(JobEvent event) {
            return event.timestamp;
        }
    }

    private static final class LocalTextFileSink extends RichSinkFunction<String> {
        private final String outputPath;
        private transient BufferedWriter writer;

        private LocalTextFileSink(String outputPath) {
            this.outputPath = outputPath;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            File file = new File(outputPath);
            File parent = file.getParentFile();
            if (parent != null) {
                parent.mkdirs();
            }
            writer = new BufferedWriter(new FileWriter(file, false));
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
                writer = null;
            }
        }
    }
}
