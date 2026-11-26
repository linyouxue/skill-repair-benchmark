package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.functions.MapFunction;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.typeinfo.Types;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.streaming.api.functions.sink.SinkFunction;
import org.apache.flink.streaming.api.functions.source.SourceFunction;
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

    private static final long MICROS_PER_SECOND = 1_000_000L;

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        final int sesssizeSeconds = params.getInt("sesssize", 600);
        final long inactivityGapMicros = sesssizeSeconds * MICROS_PER_SECOND;

        if (taskInput == null && AppBase.taskEvents == null) {
            throw new IllegalArgumentException("Missing required parameter: task_input");
        }
        if (jobInput == null && AppBase.jobEvents == null) {
            throw new IllegalArgumentException("Missing required parameter: job_input");
        }
        if (outputPath == null && AppBase.out == null) {
            throw new IllegalArgumentException("Missing required parameter: output");
        }

        // set up streaming execution environment
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.getConfig().setGlobalJobParameters(params);
        env.getConfig().setAutoWatermarkInterval(100L);

        DataStream<TaskEvent> taskEventsStream = env
                .addSource(taskSourceOrTest(new TaskEventFileSource(taskInput)))
                .name("task-events");

        DataStream<JobEvent> jobEventsStream = env
                .addSource(jobSourceOrTest(new JobEventFileSource(jobInput)))
                .name("job-events");

        WatermarkStrategy<TaskEvent> taskWatermarks = WatermarkStrategy
                .<TaskEvent>forMonotonousTimestamps()
                .withTimestampAssigner((e, ts) -> e.timestamp);

        WatermarkStrategy<JobEvent> jobWatermarks = WatermarkStrategy
                .<JobEvent>forMonotonousTimestamps()
                .withTimestampAssigner((e, ts) -> e.timestamp);

        DataStream<TaskEvent> submits = taskEventsStream
                .assignTimestampsAndWatermarks(taskWatermarks)
                .filter(TaskEvent::isSubmit)
                .name("task-submits");

        DataStream<JobEvent> finishes = jobEventsStream
                .assignTimestampsAndWatermarks(jobWatermarks)
                .filter(JobEvent::isFinish)
                .name("job-finishes");

        DataStream<Tuple2<Long, Integer>> longestStagePerJob = submits
                .keyBy(TaskEvent::getJobId)
                .connect(finishes.keyBy(JobEvent::getJobId))
                .process(new LongestStagePerJobFunction(inactivityGapMicros))
                .name("longest-stage-per-job");

        DataStream<String> formatted = longestStagePerJob
                .map((MapFunction<Tuple2<Long, Integer>, String>) v -> "(" + v.f0 + "," + v.f1 + ")")
                .name("format-output");

        @SuppressWarnings("unchecked")
        SinkFunction<String> sink = (SinkFunction<String>) sinkOrTest(new LocalTextSink(outputPath));
        formatted.addSink(sink).name("output").setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    /**
     * Keyed by jobId.
     */
    public static class LongestStagePerJobFunction extends KeyedCoProcessFunction<Long, TaskEvent, JobEvent, Tuple2<Long, Integer>> {

        private final long inactivityGapMicros;

        private transient ValueState<Long> lastSubmitTs;
        private transient ValueState<Integer> currentStageCount;
        private transient ValueState<Integer> longestStageCount;
        private transient ValueState<Long> finishTs;

        public LongestStagePerJobFunction(long inactivityGapMicros) {
            this.inactivityGapMicros = inactivityGapMicros;
        }

        @Override
        public void open(Configuration parameters) {
            lastSubmitTs = getRuntimeContext().getState(new ValueStateDescriptor<>("lastSubmitTs", Types.LONG));
            currentStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("currentStageCount", Types.INT));
            longestStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("longestStageCount", Types.INT));
            finishTs = getRuntimeContext().getState(new ValueStateDescriptor<>("finishTs", Types.LONG));
        }

        @Override
        public void processElement1(TaskEvent submit, Context ctx, Collector<Tuple2<Long, Integer>> out) throws Exception {
            Long finishedAt = finishTs.value();
            if (finishedAt != null && submit.timestamp > finishedAt) {
                return;
            }

            Long lastTs = lastSubmitTs.value();
            Integer current = currentStageCount.value();
            Integer longest = longestStageCount.value();

            int currentVal = current == null ? 0 : current;
            int longestVal = longest == null ? 0 : longest;

            if (lastTs == null) {
                currentVal = 1;
            } else {
                long gap = submit.timestamp - lastTs;
                if (gap > inactivityGapMicros) {
                    if (currentVal > longestVal) {
                        longestVal = currentVal;
                    }
                    currentVal = 1;
                } else {
                    currentVal += 1;
                }
            }

            lastSubmitTs.update(submit.timestamp);
            currentStageCount.update(currentVal);
            longestStageCount.update(longestVal);
        }

        @Override
        public void processElement2(JobEvent jobFinish, Context ctx, Collector<Tuple2<Long, Integer>> out) throws Exception {
            Long existingFinishTs = finishTs.value();
            if (existingFinishTs == null || jobFinish.timestamp > existingFinishTs) {
                finishTs.update(jobFinish.timestamp);
                ctx.timerService().registerEventTimeTimer(jobFinish.timestamp);
            }
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Integer>> out) throws Exception {
            Long finishedAt = finishTs.value();
            if (finishedAt == null || timestamp != finishedAt) {
                return;
            }

            Integer current = currentStageCount.value();
            Integer longest = longestStageCount.value();

            int currentVal = current == null ? 0 : current;
            int longestVal = longest == null ? 0 : longest;
            int maxStage = Math.max(currentVal, longestVal);

            if (maxStage > 0) {
                out.collect(Tuple2.of(ctx.getCurrentKey(), maxStage));
            }

            lastSubmitTs.clear();
            currentStageCount.clear();
            longestStageCount.clear();
            finishTs.clear();
        }
    }

    public static class TaskEventFileSource implements SourceFunction<TaskEvent> {

        private final String path;
        private volatile boolean running = true;

        public TaskEventFileSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<TaskEvent> ctx) throws Exception {
            if (path == null) {
                return;
            }
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(openInput(path), StandardCharsets.UTF_8))) {
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

    public static class JobEventFileSource implements SourceFunction<JobEvent> {

        private final String path;
        private volatile boolean running = true;

        public JobEventFileSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<JobEvent> ctx) throws Exception {
            if (path == null) {
                return;
            }
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(openInput(path), StandardCharsets.UTF_8))) {
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

    private static InputStream openInput(String path) throws Exception {
        InputStream in = new FileInputStream(path);
        if (path.endsWith(".gz")) {
            return new GZIPInputStream(in);
        }
        return in;
    }

    /**
     * Simple single-file sink, used when tests don't inject their own sink.
     */
    public static class LocalTextSink extends RichSinkFunction<String> {

        private final String outputPath;
        private transient BufferedWriter writer;

        public LocalTextSink(String outputPath) {
            this.outputPath = outputPath;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            if (outputPath == null) {
                throw new IllegalArgumentException("Missing required parameter: output");
            }

            File file = new File(outputPath);
            File parent = file.getParentFile();
            if (parent != null && !parent.exists()) {
                //noinspection ResultOfMethodCallIgnored
                parent.mkdirs();
            }

            writer = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(file, false), StandardCharsets.UTF_8));
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
