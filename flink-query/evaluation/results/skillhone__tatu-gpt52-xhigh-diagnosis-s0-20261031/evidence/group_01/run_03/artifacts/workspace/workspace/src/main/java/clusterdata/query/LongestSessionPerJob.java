package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import org.apache.flink.api.common.functions.AggregateFunction;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.streaming.api.functions.sink.SinkFunction;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.streaming.api.functions.source.SourceFunction;
import org.apache.flink.streaming.api.watermark.Watermark;

import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.streaming.api.windowing.assigners.EventTimeSessionWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;

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

public class LongestSessionPerJob extends AppBase {

    private static final int TASK_EVENT_TYPE_SUBMIT = 0;
    private static final int JOB_EVENT_TYPE_FAIL = 3;
    private static final int JOB_EVENT_TYPE_FINISH = 4;
    private static final int JOB_EVENT_TYPE_KILL = 5;
    private static final int JOB_EVENT_TYPE_LOST = 6;

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);

        final int sesssize = params.getInt("sesssize", 600);

        // set up streaming execution environment
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);

        boolean hasTaskSource = AppBase.taskEvents != null || taskInput != null;
        boolean hasJobSource = AppBase.jobEvents != null || jobInput != null;
        boolean hasSink = AppBase.out != null || outputPath != null;

        if (!hasTaskSource || !hasJobSource || !hasSink) {
            throw new IllegalArgumentException("Missing required parameters: task_input, job_input, output");
        }

        DataStream<TaskEvent> taskEvents =
                env.addSource(taskSourceOrTest(new TaskEventSource(taskInput)));

        DataStream<JobEvent> jobEvents =
                env.addSource(jobSourceOrTest(new JobEventSource(jobInput)));

        DataStream<Tuple2<Long, Long>> sessionCounts = taskEvents
                .filter(e -> e.eventType == TASK_EVENT_TYPE_SUBMIT)
                .keyBy(e -> e.jobId)
                .window(EventTimeSessionWindows.withGap(Time.seconds(sesssize)))
                .aggregate(new CountAgg(), new SessionCountToTuple());

        DataStream<JobEvent> terminalJobs = jobEvents
                .filter(e ->
                        e.eventType == JOB_EVENT_TYPE_FAIL
                                || e.eventType == JOB_EVENT_TYPE_FINISH
                                || e.eventType == JOB_EVENT_TYPE_KILL
                                || e.eventType == JOB_EVENT_TYPE_LOST);

        DataStream<Tuple2<Long, Long>> longestSessionPerTerminalJob = sessionCounts
                .keyBy(t -> t.f0)
                .connect(terminalJobs.keyBy(e -> e.jobId))
                .process(new MaxStageUntilTerminal());

        SinkFunction<Tuple2<Long, Long>> sink = (SinkFunction<Tuple2<Long, Long>>) sinkOrTest(new LocalTupleSink(outputPath));
        longestSessionPerTerminalJob.addSink(sink).setParallelism(1);

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

    private static final class SessionCountToTuple extends ProcessWindowFunction<Long, Tuple2<Long, Long>, Long, TimeWindow> {
        @Override
        public void process(Long key, Context context, Iterable<Long> elements, Collector<Tuple2<Long, Long>> out) {
            Long cnt = elements.iterator().next();
            out.collect(Tuple2.of(key, cnt));
        }
    }

    private static final class MaxStageUntilTerminal
            extends KeyedCoProcessFunction<Long, Tuple2<Long, Long>, JobEvent, Tuple2<Long, Long>> {

        private static final long END_OF_INPUT_TIMER_TS = Long.MAX_VALUE - 1;

        private transient ValueState<Long> maxStageCount;
        private transient ValueState<Boolean> terminalSeen;
        private transient ValueState<Boolean> endTimerRegistered;

        @Override
        public void open(Configuration parameters) {
            maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Long.class));
            terminalSeen = getRuntimeContext().getState(new ValueStateDescriptor<>("terminalSeen", Boolean.class));
            endTimerRegistered = getRuntimeContext().getState(new ValueStateDescriptor<>("endTimerRegistered", Boolean.class));
        }

        @Override
        public void processElement1(Tuple2<Long, Long> value, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            Long current = maxStageCount.value();
            if (current == null || value.f1 > current) {
                maxStageCount.update(value.f1);
            }
            registerEndTimerIfNeeded(ctx);
        }

        @Override
        public void processElement2(JobEvent value, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            terminalSeen.update(true);
            registerEndTimerIfNeeded(ctx);
        }

        private void registerEndTimerIfNeeded(Context ctx) throws Exception {
            Boolean registered = endTimerRegistered.value();
            if (registered == null || !registered) {
                ctx.timerService().registerEventTimeTimer(END_OF_INPUT_TIMER_TS);
                endTimerRegistered.update(true);
            }
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            if (Boolean.TRUE.equals(terminalSeen.value())) {
                Long max = maxStageCount.value();
                out.collect(Tuple2.of(ctx.getCurrentKey(), max == null ? 0L : max));
            }
            maxStageCount.clear();
            terminalSeen.clear();
            endTimerRegistered.clear();
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
            long lastEmittedWatermark = Long.MIN_VALUE;
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(openInput(path), StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }
                    TaskEvent event = TaskEvent.fromCsv(line);
                    long ts = event.timestampUs / 1000L;
                    synchronized (ctx.getCheckpointLock()) {
                        ctx.collectWithTimestamp(event, ts);
                        if (ts > lastEmittedWatermark) {
                            ctx.emitWatermark(new Watermark(ts));
                            lastEmittedWatermark = ts;
                        }
                    }
                }
            }
            synchronized (ctx.getCheckpointLock()) {
                ctx.emitWatermark(Watermark.MAX_WATERMARK);
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
            long lastEmittedWatermark = Long.MIN_VALUE;
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(openInput(path), StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }
                    JobEvent event = JobEvent.fromCsv(line);
                    long ts = event.timestampUs / 1000L;
                    synchronized (ctx.getCheckpointLock()) {
                        ctx.collectWithTimestamp(event, ts);
                        if (ts > lastEmittedWatermark) {
                            ctx.emitWatermark(new Watermark(ts));
                            lastEmittedWatermark = ts;
                        }
                    }
                }
            }
            synchronized (ctx.getCheckpointLock()) {
                ctx.emitWatermark(Watermark.MAX_WATERMARK);
            }
        }

        @Override
        public void cancel() {
            running = false;
        }
    }

    private static InputStream openInput(String path) throws Exception {
        InputStream in = new FileInputStream(path);
        if (path.endsWith(".gz")) {
            return new GZIPInputStream(in);
        }
        return in;
    }

    private static final class LocalTupleSink extends RichSinkFunction<Tuple2<Long, Long>> {

        private final String outputPath;
        private transient BufferedWriter writer;

        private LocalTupleSink(String outputPath) {
            this.outputPath = outputPath;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            File file = new File(outputPath);
            File parent = file.getParentFile();
            if (parent != null && !parent.exists()) {
                parent.mkdirs();
            }
            writer = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(file, false), StandardCharsets.UTF_8));
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
