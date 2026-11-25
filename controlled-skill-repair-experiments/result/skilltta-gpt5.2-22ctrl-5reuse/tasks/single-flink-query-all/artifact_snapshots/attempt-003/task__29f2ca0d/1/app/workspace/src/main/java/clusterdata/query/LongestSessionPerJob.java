package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.zip.GZIPInputStream;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.functions.AggregateFunction;
import org.apache.flink.api.common.functions.FilterFunction;
import org.apache.flink.api.common.functions.MapFunction;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.java.functions.KeySelector;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.datastream.ConnectedStreams;
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
        System.out.println("task_input  " + taskInput);
        System.out.println("job_input  " + jobInput);

        // Session size is in seconds. Default 600s = 10 minutes.
        final int sesssize = params.getInt("sesssize", 600);

        if (taskInput == null || jobInput == null) {
            throw new IllegalArgumentException("task_input and job_input parameters are required");
        }

        // set up streaming execution environment
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        DataStream<TaskEvent> tasks =
                env.addSource(taskSourceOrTest(new TaskEventSource(taskInput)))
                        .assignTimestampsAndWatermarks(taskWatermarks());

        DataStream<JobEvent> jobs =
                env.addSource(jobSourceOrTest(new JobEventSource(jobInput)))
                        .assignTimestampsAndWatermarks(jobWatermarks());

        SingleOutputStreamOperator<Tuple2<Long, Integer>> stageCounts =
                tasks.filter(new IsSubmitTaskEvent())
                        .keyBy(new TaskJobIdKeySelector())
                        .window(EventTimeSessionWindows.withGap(Time.seconds(sesssize)))
                        .aggregate(new SubmitCountAgg(), new StageCountWindowResult());

        DataStream<Long> finishedJobs = jobs.filter(new IsTerminalJobEvent()).map(new JobIdMap());

        ConnectedStreams<Tuple2<Long, Integer>, Long> connected =
                stageCounts
                        .connect(finishedJobs)
                        .keyBy(new TupleJobIdKeySelector(), new LongIdentityKeySelector());

        SingleOutputStreamOperator<Tuple2<Long, Integer>> finishedMax =
                connected.process(new MaxStageWhenFinished());

        DataStream<String> formatted = finishedMax.map(new TupleToStringMap());

        if (outputPath != null) {
            // Use a raw SinkFunction cast to remain compatible with test sinks.
            @SuppressWarnings({"rawtypes", "unchecked"})
            SinkFunction sink = (SinkFunction) sinkOrTest(new LocalFileSink(outputPath));
            formatted.addSink(sink).setParallelism(1);
        } else {
            formatted.print();
        }

        env.execute("LongestSessionPerJob");
    }

    private static WatermarkStrategy<TaskEvent> taskWatermarks() {
        return WatermarkStrategy.<TaskEvent>forBoundedOutOfOrderness(Duration.ZERO)
                .withTimestampAssigner((event, recordTs) -> event.getTimestampMillis());
    }

    private static WatermarkStrategy<JobEvent> jobWatermarks() {
        return WatermarkStrategy.<JobEvent>forBoundedOutOfOrderness(Duration.ZERO)
                .withTimestampAssigner((event, recordTs) -> event.getTimestampMillis());
    }

    private static class SubmitCountAgg implements AggregateFunction<TaskEvent, Long, Long> {
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

    private static class StageCountWindowResult
            extends ProcessWindowFunction<Long, Tuple2<Long, Integer>, Long, TimeWindow> {
        @Override
        public void process(
                Long jobId,
                Context context,
                Iterable<Long> elements,
                Collector<Tuple2<Long, Integer>> out) {
            Long count = elements.iterator().next();
            out.collect(Tuple2.of(jobId, count.intValue()));
        }
    }

    private static final class IsSubmitTaskEvent implements FilterFunction<TaskEvent> {
        @Override
        public boolean filter(TaskEvent value) {
            return value.isSubmitEvent();
        }
    }

    private static final class TaskJobIdKeySelector implements KeySelector<TaskEvent, Long> {
        @Override
        public Long getKey(TaskEvent value) {
            return value.getJobId();
        }
    }

    private static final class TupleJobIdKeySelector implements KeySelector<Tuple2<Long, Integer>, Long> {
        @Override
        public Long getKey(Tuple2<Long, Integer> value) {
            return value.f0;
        }
    }

    private static final class LongIdentityKeySelector implements KeySelector<Long, Long> {
        @Override
        public Long getKey(Long value) {
            return value;
        }
    }


    private static final class IsTerminalJobEvent implements FilterFunction<JobEvent> {
        @Override
        public boolean filter(JobEvent value) {
            return value.isTerminalEvent();
        }
    }

    private static final class JobIdMap implements MapFunction<JobEvent, Long> {
        @Override
        public Long map(JobEvent value) {
            return value.getJobId();
        }
    }

    private static final class TupleToStringMap implements MapFunction<Tuple2<Long, Integer>, String> {
        @Override
        public String map(Tuple2<Long, Integer> value) {
            return value.toString();
        }
    }

    /**
     * Joins stage counts with job termination, and emits one tuple per job.
     */
    private static class MaxStageWhenFinished
            extends KeyedCoProcessFunction<Long, Tuple2<Long, Integer>, Long, Tuple2<Long, Integer>> {

        private transient ValueState<Integer> maxStageCount;
        private transient ValueState<Boolean> isFinished;
        private transient ValueState<Boolean> emitted;
        private transient ValueState<Boolean> timerRegistered;

        @Override
        public void open(Configuration parameters) {
            maxStageCount =
                    getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Integer.class));
            isFinished = getRuntimeContext().getState(new ValueStateDescriptor<>("isFinished", Boolean.class));
            emitted = getRuntimeContext().getState(new ValueStateDescriptor<>("emitted", Boolean.class));
            timerRegistered =
                    getRuntimeContext().getState(new ValueStateDescriptor<>("timerRegistered", Boolean.class));
        }

        @Override
        public void processElement1(
                Tuple2<Long, Integer> value, Context ctx, Collector<Tuple2<Long, Integer>> out)
                throws Exception {
            Integer currentMax = maxStageCount.value();
            if (currentMax == null || value.f1 > currentMax) {
                maxStageCount.update(value.f1);
            }
            registerTimerOnce(ctx);
        }

        @Override
        public void processElement2(Long value, Context ctx, Collector<Tuple2<Long, Integer>> out)
                throws Exception {
            isFinished.update(true);
            registerTimerOnce(ctx);
        }

        private void registerTimerOnce(Context ctx) throws Exception {
            Boolean registered = timerRegistered.value();
            if (registered == null || !registered) {
                ctx.timerService().registerEventTimeTimer(Long.MAX_VALUE);
                timerRegistered.update(true);
            }
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Integer>> out)
                throws Exception {
            Boolean alreadyEmitted = emitted.value();
            if (alreadyEmitted != null && alreadyEmitted) {
                return;
            }

            Boolean finished = isFinished.value();
            if (finished == null || !finished) {
                return;
            }

            Integer max = maxStageCount.value();
            out.collect(Tuple2.of(ctx.getCurrentKey(), max == null ? 0 : max));
            emitted.update(true);
        }
    }

    private static final class TaskEventSource implements SourceFunction<TaskEvent> {
        private final String path;
        private volatile boolean running = true;

        private TaskEventSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<TaskEvent> ctx) throws Exception {
            try (InputStream is = openPossiblyGzipped(path);
                    BufferedReader reader =
                            new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }
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

    private static final class JobEventSource implements SourceFunction<JobEvent> {
        private final String path;
        private volatile boolean running = true;

        private JobEventSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<JobEvent> ctx) throws Exception {
            try (InputStream is = openPossiblyGzipped(path);
                    BufferedReader reader =
                            new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }
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

    private static InputStream openPossiblyGzipped(String path) throws IOException {
        Path p = toPath(path);
        InputStream is = Files.newInputStream(p);
        if (path.endsWith(".gz")) {
            return new GZIPInputStream(is);
        }
        return is;
    }

    private static Path toPath(String path) {
        if (path.startsWith("file:")) {
            return Paths.get(java.net.URI.create(path));
        }
        return Paths.get(path);
    }

    private static final class LocalFileSink extends RichSinkFunction<String> {
        private final String path;
        private transient BufferedWriter writer;

        private LocalFileSink(String path) {
            this.path = path;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            Path p = toPath(path);
            Path parent = p.getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }
            writer =
                    new BufferedWriter(
                            new OutputStreamWriter(Files.newOutputStream(p), StandardCharsets.UTF_8));
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
