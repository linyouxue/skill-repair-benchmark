package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.zip.GZIPInputStream;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.functions.AggregateFunction;
import org.apache.flink.api.common.functions.MapFunction;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.datastream.SingleOutputStreamOperator;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.streaming.api.functions.sink.SinkFunction;
import org.apache.flink.streaming.api.functions.source.SourceFunction;
import org.apache.flink.streaming.api.windowing.assigners.EventTimeSessionWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.util.Collector;

public class LongestSessionPerJob extends AppBase {

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        final int sesssize = params.getInt("sesssize", 600);

        if (taskInput == null || jobInput == null || outputPath == null) {
            throw new IllegalArgumentException("Required parameters: task_input, job_input, output");
        }

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);

        DataStream<TaskEvent> taskEvents = env
                .addSource(taskSourceOrTest(new GzipTaskEventSource(taskInput)))
                .name("task-events");

        WatermarkStrategy<TaskEvent> taskWm = WatermarkStrategy
                .<TaskEvent>forMonotonousTimestamps()
                .withTimestampAssigner((e, ts) -> e.timestampMs);

        SingleOutputStreamOperator<TaskEvent> submitTasks = taskEvents
                .filter(e -> e != null && e.eventType == TaskEvent.EVENT_SUBMIT)
                .assignTimestampsAndWatermarks(taskWm);

        SingleOutputStreamOperator<Tuple2<Long, Long>> stageCounts = submitTasks
                .keyBy(e -> e.jobId)
                .window(EventTimeSessionWindows.withGap(Time.seconds(sesssize)))
                .aggregate(new CountAgg(), new WindowToJobCount());

        DataStream<JobEvent> jobEvents = env
                .addSource(jobSourceOrTest(new GzipJobEventSource(jobInput)))
                .name("job-events");

        WatermarkStrategy<JobEvent> jobWm = WatermarkStrategy
                .<JobEvent>forMonotonousTimestamps()
                .withTimestampAssigner((e, ts) -> e.timestampMs);

        SingleOutputStreamOperator<Tuple2<Long, Long>> jobMarkers = jobEvents
                .filter(e -> e != null)
                .assignTimestampsAndWatermarks(jobWm)
                .map(new MapFunction<JobEvent, Tuple2<Long, Long>>() {
                    @Override
                    public Tuple2<Long, Long> map(JobEvent value) {
                        return Tuple2.of(value.jobId, 0L);
                    }
                });

        SingleOutputStreamOperator<Tuple2<Long, Long>> longestPerJob = stageCounts
                .connect(jobMarkers)
                .keyBy(v -> v.f0, v -> v.f0)
                .process(new LongestStageAtEnd());

        @SuppressWarnings("unchecked")
        SinkFunction<Tuple2<Long, Long>> sink = (SinkFunction<Tuple2<Long, Long>>) sinkOrTest(new LocalTuple2FileSink(outputPath));

        longestPerJob.addSink(sink).name("output").setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    private static final class CountAgg implements AggregateFunction<TaskEvent, Long, Long> {

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

    private static final class WindowToJobCount extends ProcessWindowFunction<Long, Tuple2<Long, Long>, Long, TimeWindow> {

        @Override
        public void process(Long key, Context context, Iterable<Long> elements, Collector<Tuple2<Long, Long>> out) {
            Long count = elements.iterator().next();
            out.collect(Tuple2.of(key, count));
        }
    }

    private static final class LongestStageAtEnd
            extends KeyedCoProcessFunction<Long, Tuple2<Long, Long>, Tuple2<Long, Long>, Tuple2<Long, Long>> {

        private transient ValueState<Long> maxStageCount;
        private transient ValueState<Boolean> timerRegistered;

        @Override
        public void open(Configuration parameters) {
            maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Long.class));
            timerRegistered = getRuntimeContext().getState(new ValueStateDescriptor<>("timerRegistered", Boolean.class));
        }

        private void ensureTimerRegistered(Context ctx) throws Exception {
            Boolean registered = timerRegistered.value();
            if (registered == null || !registered) {
                ctx.timerService().registerEventTimeTimer(Long.MAX_VALUE);
                timerRegistered.update(true);
            }
        }

        @Override
        public void processElement1(Tuple2<Long, Long> value, Context ctx, Collector<Tuple2<Long, Long>> out)
                throws Exception {
            Long current = maxStageCount.value();
            long next = current == null ? value.f1 : Math.max(current, value.f1);
            maxStageCount.update(next);
            ensureTimerRegistered(ctx);
        }

        @Override
        public void processElement2(Tuple2<Long, Long> value, Context ctx, Collector<Tuple2<Long, Long>> out)
                throws Exception {
            if (maxStageCount.value() == null) {
                maxStageCount.update(0L);
            }
            ensureTimerRegistered(ctx);
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            Long max = maxStageCount.value();
            out.collect(Tuple2.of(ctx.getCurrentKey(), max == null ? 0L : max));
            maxStageCount.clear();
            timerRegistered.clear();
        }
    }

    private static final class GzipTaskEventSource implements SourceFunction<TaskEvent> {

        private final String path;
        private volatile boolean running = true;

        private GzipTaskEventSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<TaskEvent> ctx) throws Exception {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                    new GZIPInputStream(new FileInputStream(path)), StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    TaskEvent event;
                    try {
                        event = TaskEvent.fromCsvLine(line);
                    } catch (Exception ignored) {
                        continue;
                    }

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

    private static final class GzipJobEventSource implements SourceFunction<JobEvent> {

        private final String path;
        private volatile boolean running = true;

        private GzipJobEventSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<JobEvent> ctx) throws Exception {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                    new GZIPInputStream(new FileInputStream(path)), StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    JobEvent event;
                    try {
                        event = JobEvent.fromCsvLine(line);
                    } catch (Exception ignored) {
                        continue;
                    }

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

    private static final class LocalTuple2FileSink extends RichSinkFunction<Tuple2<Long, Long>> {

        private final String outputPath;
        private transient BufferedWriter writer;

        private LocalTuple2FileSink(String outputPath) {
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
