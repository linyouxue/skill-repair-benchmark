package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.functions.AggregateFunction;
import org.apache.flink.api.common.functions.MapFunction;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.core.fs.FSDataInputStream;
import org.apache.flink.core.fs.FileSystem;
import org.apache.flink.core.fs.Path;
import org.apache.flink.streaming.api.datastream.ConnectedStreams;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.streaming.api.functions.source.SourceFunction;
import org.apache.flink.streaming.api.windowing.assigners.EventTimeSessionWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.util.Collector;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
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

        if (taskInput == null || jobInput == null || outputPath == null) {
            throw new IllegalArgumentException("Parameters task_input, job_input and output are required.");
        }

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);

        DataStream<TaskEvent> taskEventsStream = env
                .addSource(taskSourceOrTest(new TaskEventSource(taskInput)))
                .name("task-events");

        DataStream<JobEvent> jobEventsStream = env
                .addSource(jobSourceOrTest(new JobEventSource(jobInput)))
                .name("job-events");

        WatermarkStrategy<TaskEvent> taskWm = WatermarkStrategy
                .<TaskEvent>forMonotonousTimestamps()
                .withTimestampAssigner((e, ts) -> e.timestampMs);

        WatermarkStrategy<JobEvent> jobWm = WatermarkStrategy
                .<JobEvent>forMonotonousTimestamps()
                .withTimestampAssigner((e, ts) -> e.timestampMs);

        DataStream<TaskEvent> submitEvents = taskEventsStream
                .assignTimestampsAndWatermarks(taskWm)
                .filter(e -> e.eventType == TaskEvent.EVENT_SUBMIT)
                .name("submit-task-events");

        DataStream<StageCount> stageCounts = submitEvents
                .keyBy(e -> e.jobId)
                .window(EventTimeSessionWindows.withGap(Time.seconds(sesssize)))
                .aggregate(new CountAgg(), new StageCountWindowFunction())
                .name("stage-counts");

        DataStream<JobEnd> jobEnds = jobEventsStream
                .assignTimestampsAndWatermarks(jobWm)
                .filter(JobEvent::isTerminalEvent)
                .map((MapFunction<JobEvent, JobEnd>) value -> new JobEnd(value.jobId))
                .name("job-ends");

        ConnectedStreams<StageCount, JobEnd> connected = stageCounts
                .keyBy(s -> s.jobId)
                .connect(jobEnds.keyBy(j -> j.jobId));

        DataStream<Tuple2<Long, Long>> longestStagePerJob = connected
                .process(new LongestStageOnJobEnd())
                .name("longest-stage-per-job");

        @SuppressWarnings("unchecked")
        org.apache.flink.streaming.api.functions.sink.SinkFunction<Tuple2<Long, Long>> sink =
                (org.apache.flink.streaming.api.functions.sink.SinkFunction<Tuple2<Long, Long>>) sinkOrTest(new LocalFileSink(outputPath));

        longestStagePerJob
                .addSink(sink)
                .name("file-sink")
                .setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    public static class StageCount {
        public long jobId;
        public long count;

        public StageCount() {
        }

        public StageCount(long jobId, long count) {
            this.jobId = jobId;
            this.count = count;
        }
    }

    public static class JobEnd {
        public long jobId;

        public JobEnd() {
        }

        public JobEnd(long jobId) {
            this.jobId = jobId;
        }
    }

    public static class CountAgg implements AggregateFunction<TaskEvent, Long, Long> {

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

    public static class StageCountWindowFunction extends ProcessWindowFunction<Long, StageCount, Long, TimeWindow> {

        @Override
        public void process(Long key, Context context, Iterable<Long> elements, Collector<StageCount> out) {
            long count = elements.iterator().next();
            out.collect(new StageCount(key, count));
        }
    }

    public static class LongestStageOnJobEnd extends KeyedCoProcessFunction<Long, StageCount, JobEnd, Tuple2<Long, Long>> {

        private transient ValueState<Long> maxStageCount;
        private transient ValueState<Boolean> jobEnded;
        private transient ValueState<Boolean> timerRegistered;

        @Override
        public void open(Configuration parameters) {
            maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Long.class));
            jobEnded = getRuntimeContext().getState(new ValueStateDescriptor<>("jobEnded", Boolean.class));
            timerRegistered = getRuntimeContext().getState(new ValueStateDescriptor<>("timerRegistered", Boolean.class));
        }

        @Override
        public void processElement1(StageCount value, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            Long current = maxStageCount.value();
            if (current == null || value.count > current) {
                maxStageCount.update(value.count);
            }
            registerTimerIfNeeded(ctx);
        }

        @Override
        public void processElement2(JobEnd value, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            jobEnded.update(true);
            registerTimerIfNeeded(ctx);
        }

        private void registerTimerIfNeeded(Context ctx) throws Exception {
            Boolean registered = timerRegistered.value();
            if (registered == null || !registered) {
                ctx.timerService().registerEventTimeTimer(END_OF_STREAM_TIMER);
                timerRegistered.update(true);
            }
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            if (Boolean.TRUE.equals(jobEnded.value())) {
                Long max = maxStageCount.value();
                out.collect(Tuple2.of(ctx.getCurrentKey(), max == null ? 0L : max));
            }
            maxStageCount.clear();
            jobEnded.clear();
            timerRegistered.clear();
        }
    }

    public static class TaskEventSource implements SourceFunction<TaskEvent> {

        private final String path;
        private volatile boolean running = true;

        public TaskEventSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<TaskEvent> ctx) throws Exception {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(openPossiblyCompressed(path), StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    TaskEvent event = TaskEvent.fromCsvLine(line);
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

    public static class JobEventSource implements SourceFunction<JobEvent> {

        private final String path;
        private volatile boolean running = true;

        public JobEventSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<JobEvent> ctx) throws Exception {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(openPossiblyCompressed(path), StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    JobEvent event = JobEvent.fromCsvLine(line);
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

    private static InputStream openPossiblyCompressed(String pathStr) throws IOException {
        Path path = new Path(pathStr);
        FileSystem fs = path.getFileSystem();
        FSDataInputStream in = fs.open(path);
        if (pathStr.endsWith(".gz")) {
            return new GZIPInputStream(in);
        }
        return in;
    }

    public static class LocalFileSink extends RichSinkFunction<Tuple2<Long, Long>> {

        private final String outputPath;
        private transient java.io.BufferedWriter writer;

        public LocalFileSink(String outputPath) {
            this.outputPath = outputPath;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            java.nio.file.Path p = Paths.get(outputPath);
            java.nio.file.Path parent = p.getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }
            writer = Files.newBufferedWriter(p, StandardCharsets.UTF_8);
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
