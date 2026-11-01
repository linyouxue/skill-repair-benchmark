package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.zip.GZIPInputStream;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.functions.AggregateFunction;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.streaming.api.functions.source.SourceFunction;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
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

        if (taskInput == null && AppBase.taskEvents == null) {
            throw new IllegalArgumentException("Missing required parameter: task_input");
        }
        if (jobInput == null && AppBase.jobEvents == null) {
            throw new IllegalArgumentException("Missing required parameter: job_input");
        }
        if (outputPath == null && AppBase.out == null) {
            throw new IllegalArgumentException("Missing required parameter: output");
        }

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        DataStream<TaskEvent> tasks = env.addSource(taskSourceOrTest(new TaskEventSource(taskInput)));
        DataStream<JobEvent> jobs = env.addSource(jobSourceOrTest(new JobEventSource(jobInput)));

        WatermarkStrategy<TaskEvent> taskWm = WatermarkStrategy.<TaskEvent>forMonotonousTimestamps()
                .withTimestampAssigner((e, ts) -> e.getTimestampMillis());

        WatermarkStrategy<JobEvent> jobWm = WatermarkStrategy.<JobEvent>forMonotonousTimestamps()
                .withTimestampAssigner((e, ts) -> e.getTimestampMillis());

        DataStream<TaskEvent> submitEvents = tasks
                .filter(e -> e.eventType == TaskEvent.EVENT_SUBMIT)
                .assignTimestampsAndWatermarks(taskWm);

        DataStream<Tuple2<Long, Long>> stageCounts = submitEvents
                .keyBy(e -> e.jobId)
                .window(EventTimeSessionWindows.withGap(Time.seconds(sesssize)))
                .aggregate(new CountAgg(), new StageCountWindowFn());

        DataStream<Long> terminalJobs = jobs
                .assignTimestampsAndWatermarks(jobWm)
                .filter(JobEvent::isTerminal)
                .map(e -> e.jobId);

        DataStream<Tuple2<Long, Long>> longestStagePerFinishedJob = stageCounts
                .keyBy(t -> t.f0)
                .connect(terminalJobs.keyBy(id -> id))
                .process(new EmitMaxStageOnEnd());

        @SuppressWarnings("unchecked")
        org.apache.flink.streaming.api.functions.sink.SinkFunction<Tuple2<Long, Long>> sink =
                (org.apache.flink.streaming.api.functions.sink.SinkFunction<Tuple2<Long, Long>>)
                        sinkOrTest(new LocalTextFileSink(outputPath));
        longestStagePerFinishedJob.addSink(sink).setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    private static final class TaskEventSource implements SourceFunction<TaskEvent> {

        private final String path;
        private volatile boolean running = true;

        private TaskEventSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<TaskEvent> ctx) throws Exception {
            InputStream inputStream = new FileInputStream(path);
            if (path.endsWith(".gz")) {
                inputStream = new GZIPInputStream(inputStream);
            }

            try (BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream, StandardCharsets.UTF_8))) {
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

    private static final class JobEventSource implements SourceFunction<JobEvent> {

        private final String path;
        private volatile boolean running = true;

        private JobEventSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<JobEvent> ctx) throws Exception {
            InputStream inputStream = new FileInputStream(path);
            if (path.endsWith(".gz")) {
                inputStream = new GZIPInputStream(inputStream);
            }

            try (BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream, StandardCharsets.UTF_8))) {
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

    private static final class StageCountWindowFn
            extends ProcessWindowFunction<Long, Tuple2<Long, Long>, Long, TimeWindow> {

        @Override
        public void process(
                Long jobId,
                Context context,
                Iterable<Long> elements,
                Collector<Tuple2<Long, Long>> out) {
            Long count = elements.iterator().next();
            out.collect(Tuple2.of(jobId, count));
        }
    }

    private static final class EmitMaxStageOnEnd
            extends KeyedCoProcessFunction<Long, Tuple2<Long, Long>, Long, Tuple2<Long, Long>> {

        private transient ValueState<Long> maxStageCount;
        private transient ValueState<Boolean> jobFinished;
        private transient ValueState<Boolean> emitted;

        @Override
        public void open(Configuration parameters) {
            maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Long.class));
            jobFinished = getRuntimeContext().getState(new ValueStateDescriptor<>("jobFinished", Boolean.class));
            emitted = getRuntimeContext().getState(new ValueStateDescriptor<>("emitted", Boolean.class));
        }

        @Override
        public void processElement1(
                Tuple2<Long, Long> value,
                Context ctx,
                Collector<Tuple2<Long, Long>> out) throws Exception {
            Long currentMax = maxStageCount.value();
            long updatedMax = currentMax == null ? value.f1 : Math.max(currentMax, value.f1);
            maxStageCount.update(updatedMax);
        }

        @Override
        public void processElement2(Long value, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            jobFinished.update(true);
            ctx.timerService().registerEventTimeTimer(Long.MAX_VALUE);
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            if (!Boolean.TRUE.equals(jobFinished.value()) || Boolean.TRUE.equals(emitted.value())) {
                return;
            }

            Long max = maxStageCount.value();
            out.collect(Tuple2.of(ctx.getCurrentKey(), max == null ? 0L : max));
            emitted.update(true);
        }
    }

    private static final class LocalTextFileSink extends RichSinkFunction<Tuple2<Long, Long>> {

        private final String path;
        private transient BufferedWriter writer;

        private LocalTextFileSink(String path) {
            this.path = path;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            super.open(parameters);
            if (path == null) {
                throw new IllegalArgumentException("Output path is null");
            }

            File file = new File(path);
            File parent = file.getParentFile();
            if (parent != null) {
                parent.mkdirs();
            }

            writer = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(file, false), StandardCharsets.UTF_8));
        }

        @Override
        public synchronized void invoke(Tuple2<Long, Long> value, Context context) throws Exception {
            writer.write(value.toString());
            writer.newLine();
        }

        @Override
        public void close() throws Exception {
            if (writer != null) {
                writer.flush();
                writer.close();
            }
            super.close();
        }
    }
}
