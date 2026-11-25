package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.functions.FilterFunction;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.core.fs.FSDataInputStream;
import org.apache.flink.core.fs.FSDataOutputStream;
import org.apache.flink.core.fs.FileSystem;
import org.apache.flink.core.fs.Path;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.streaming.api.functions.source.RichSourceFunction;
import org.apache.flink.util.Collector;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.api.common.RuntimeExecutionMode;
import org.apache.flink.streaming.api.functions.sink.SinkFunction;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.zip.GZIPInputStream;

public class LongestSessionPerJob extends AppBase {

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        final int sesssize = params.getInt("sesssize", 600);

        if (taskInput == null || jobInput == null || outputPath == null) {
            throw new IllegalArgumentException(
                    "Required parameters: --task_input <path> --job_input <path> --output <path>");
        }

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setRuntimeMode(RuntimeExecutionMode.BATCH);
        env.getConfig().setAutoWatermarkInterval(1_000L);

        DataStream<TaskEvent> taskEventsStream =
                env.addSource(taskSourceOrTest(new TaskEventCsvSource(taskInput)))
                        .name("task-events");

        DataStream<JobEvent> jobEventsStream =
                env.addSource(jobSourceOrTest(new JobEventCsvSource(jobInput)))
                        .name("job-events");

        WatermarkStrategy<TaskEvent> taskWms =
                WatermarkStrategy.<TaskEvent>forMonotonousTimestamps()
                        .withTimestampAssigner((e, previous) -> e.getTimestampMillis());

        WatermarkStrategy<JobEvent> jobWms =
                WatermarkStrategy.<JobEvent>forMonotonousTimestamps()
                        .withTimestampAssigner((e, previous) -> e.getTimestampMillis());

        DataStream<TaskEvent> submitTasks =
                taskEventsStream
                        .assignTimestampsAndWatermarks(taskWms)
                        .filter((FilterFunction<TaskEvent>) e -> e.eventType == TaskEvent.EVENT_SUBMIT)
                        .name("task-submits");

        DataStream<JobEvent> terminalJobs =
                jobEventsStream
                        .assignTimestampsAndWatermarks(jobWms)
                        .filter((FilterFunction<JobEvent>) JobEvent::isTerminal)
                        .name("job-terminal");

        long gapMillis = sesssize * 1_000L;

        DataStream<String> results =
                submitTasks
                        .connect(terminalJobs)
                        .keyBy(TaskEvent::getJobId, JobEvent::getJobId)
                        .process(new LongestStagePerJobOnFinish(gapMillis))
                        .name("longest-stage-per-job");

        @SuppressWarnings("unchecked")
        SinkFunction<String> sink = (SinkFunction<String>) sinkOrTest(new LocalFileSink(outputPath));
        results.addSink(sink).setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    private static final class LongestStagePerJobOnFinish
            extends KeyedCoProcessFunction<Long, TaskEvent, JobEvent, String> {

        private final long inactivityGapMillis;

        private transient ValueState<Long> currentStageCount;
        private transient ValueState<Long> lastSubmitTs;
        private transient ValueState<Long> inactivityTimerTs;
        private transient ValueState<Long> maxStageCount;

        private transient ValueState<Long> finishTs;
        private transient ValueState<Long> finishTimerTs;
        private transient ValueState<Boolean> emitted;

        private LongestStagePerJobOnFinish(long inactivityGapMillis) {
            this.inactivityGapMillis = inactivityGapMillis;
        }

        @Override
        public void open(Configuration parameters) {
            currentStageCount =
                    getRuntimeContext()
                            .getState(new ValueStateDescriptor<>("currentStageCount", Long.class));
            lastSubmitTs =
                    getRuntimeContext().getState(new ValueStateDescriptor<>("lastSubmitTs", Long.class));
            inactivityTimerTs =
                    getRuntimeContext()
                            .getState(new ValueStateDescriptor<>("inactivityTimerTs", Long.class));
            maxStageCount =
                    getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Long.class));

            finishTs = getRuntimeContext().getState(new ValueStateDescriptor<>("finishTs", Long.class));
            finishTimerTs =
                    getRuntimeContext()
                            .getState(new ValueStateDescriptor<>("finishTimerTs", Long.class));
            emitted = getRuntimeContext().getState(new ValueStateDescriptor<>("emitted", Boolean.class));
        }

        @Override
        public void processElement1(TaskEvent event, Context ctx, Collector<String> out)
                throws Exception {
            Boolean alreadyEmitted = emitted.value();
            if (alreadyEmitted != null && alreadyEmitted) {
                return;
            }

            long ts = event.getTimestampMillis();

            Long currCount = currentStageCount.value();
            if (currCount == null) {
                currCount = 0L;
            }

            Long prevSubmit = lastSubmitTs.value();
            Long maxCount = maxStageCount.value();
            if (maxCount == null) {
                maxCount = 0L;
            }

            if (currCount > 0 && prevSubmit != null && ts - prevSubmit >= inactivityGapMillis) {
                maxCount = Math.max(maxCount, currCount);
                currCount = 0L;
            }

            currCount += 1L;
            currentStageCount.update(currCount);
            lastSubmitTs.update(ts);
            maxStageCount.update(maxCount);

            Long oldTimer = inactivityTimerTs.value();
            if (oldTimer != null) {
                ctx.timerService().deleteEventTimeTimer(oldTimer);
            }
            long newTimer = ts + inactivityGapMillis;
            ctx.timerService().registerEventTimeTimer(newTimer);
            inactivityTimerTs.update(newTimer);
        }

        @Override
        public void processElement2(JobEvent event, Context ctx, Collector<String> out)
                throws Exception {
            Boolean alreadyEmitted = emitted.value();
            if (alreadyEmitted != null && alreadyEmitted) {
                return;
            }

            long ts = event.getTimestampMillis();

            Long existingFinishTs = finishTs.value();
            if (existingFinishTs == null || ts > existingFinishTs) {
                finishTs.update(ts);
            }

            Long oldFinishTimer = finishTimerTs.value();
            long newFinishTimer = finishTs.value();
            if (oldFinishTimer != null) {
                ctx.timerService().deleteEventTimeTimer(oldFinishTimer);
            }
            ctx.timerService().registerEventTimeTimer(newFinishTimer);
            finishTimerTs.update(newFinishTimer);
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<String> out)
                throws Exception {
            Boolean alreadyEmitted = emitted.value();
            if (alreadyEmitted != null && alreadyEmitted) {
                return;
            }

            Long inactivityTimer = inactivityTimerTs.value();
            if (inactivityTimer != null && timestamp == inactivityTimer) {
                Long currCount = currentStageCount.value();
                if (currCount != null && currCount > 0) {
                    Long maxCount = maxStageCount.value();
                    if (maxCount == null) {
                        maxCount = 0L;
                    }
                    maxStageCount.update(Math.max(maxCount, currCount));
                }
                currentStageCount.clear();
                lastSubmitTs.clear();
                inactivityTimerTs.clear();
                return;
            }

            Long finishTimer = finishTimerTs.value();
            if (finishTimer != null && timestamp == finishTimer) {
                Long maxCount = maxStageCount.value();
                if (maxCount == null) {
                    maxCount = 0L;
                }

                Long currCount = currentStageCount.value();
                if (currCount != null) {
                    maxCount = Math.max(maxCount, currCount);
                }

                out.collect("(" + ctx.getCurrentKey() + "," + maxCount + ")");

                Long pendingInactivityTimer = inactivityTimerTs.value();
                if (pendingInactivityTimer != null) {
                    ctx.timerService().deleteEventTimeTimer(pendingInactivityTimer);
                }

                currentStageCount.clear();
                lastSubmitTs.clear();
                inactivityTimerTs.clear();
                maxStageCount.clear();
                finishTs.clear();
                finishTimerTs.clear();
                emitted.update(true);
            }
        }
    }

    private static final class TaskEventCsvSource extends RichSourceFunction<TaskEvent> {
        private final String path;
        private volatile boolean running = true;

        private TaskEventCsvSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<TaskEvent> ctx) throws Exception {
            Path p = new Path(path);
            FileSystem fs = p.getFileSystem();
            try (FSDataInputStream in = fs.open(p);
                    InputStream raw = wrapMaybeGzip(in, p);
                    BufferedReader br =
                            new BufferedReader(new InputStreamReader(raw, StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = br.readLine()) != null) {
                    line = line.trim();
                    if (line.isEmpty()) {
                        continue;
                    }
                    TaskEvent e = parseTaskEvent(line);
                    if (e == null) {
                        continue;
                    }
                    synchronized (ctx.getCheckpointLock()) {
                        ctx.collect(e);
                    }
                }
            }
        }

        @Override
        public void cancel() {
            running = false;
        }

        private static TaskEvent parseTaskEvent(String line) {
            String[] f = line.split(",", -1);
            if (f.length < 6) {
                return null;
            }
            try {
                long ts = Long.parseLong(f[0].trim());
                String missing = f[1];
                long jobId = Long.parseLong(f[2].trim());
                long taskIndex = parseLongOrDefault(f[3], -1L);
                long machineId = parseLongOrDefault(f[4], -1L);
                int eventType = Integer.parseInt(f[5].trim());
                return new TaskEvent(ts, missing, jobId, taskIndex, machineId, eventType);
            } catch (Exception ignored) {
                return null;
            }
        }
    }

    private static final class JobEventCsvSource extends RichSourceFunction<JobEvent> {
        private final String path;
        private volatile boolean running = true;

        private JobEventCsvSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<JobEvent> ctx) throws Exception {
            Path p = new Path(path);
            FileSystem fs = p.getFileSystem();
            try (FSDataInputStream in = fs.open(p);
                    InputStream raw = wrapMaybeGzip(in, p);
                    BufferedReader br =
                            new BufferedReader(new InputStreamReader(raw, StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = br.readLine()) != null) {
                    line = line.trim();
                    if (line.isEmpty()) {
                        continue;
                    }
                    JobEvent e = parseJobEvent(line);
                    if (e == null) {
                        continue;
                    }
                    synchronized (ctx.getCheckpointLock()) {
                        ctx.collect(e);
                    }
                }
            }
        }

        @Override
        public void cancel() {
            running = false;
        }

        private static JobEvent parseJobEvent(String line) {
            String[] f = line.split(",", -1);
            if (f.length < 4) {
                return null;
            }
            try {
                long ts = Long.parseLong(f[0].trim());
                String missing = f[1];
                long jobId = Long.parseLong(f[2].trim());
                int eventType = Integer.parseInt(f[3].trim());
                return new JobEvent(ts, missing, jobId, eventType);
            } catch (Exception ignored) {
                return null;
            }
        }
    }

    private static final class LocalFileSink extends RichSinkFunction<String> {
        private final String path;
        private transient BufferedWriter writer;

        private LocalFileSink(String path) {
            this.path = path;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            Path p = new Path(path);
            FileSystem fs = p.getFileSystem();
            Path parent = p.getParent();
            if (parent != null) {
                fs.mkdirs(parent);
            }
            if (fs.exists(p)) {
                fs.delete(p, false);
            }
            FSDataOutputStream out = fs.create(p, FileSystem.WriteMode.OVERWRITE);
            writer = new BufferedWriter(new OutputStreamWriter(out, StandardCharsets.UTF_8));
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

    private static InputStream wrapMaybeGzip(InputStream in, Path p) throws Exception {
        if (p.getName().endsWith(".gz")) {
            return new GZIPInputStream(in);
        }
        return in;
    }

    private static long parseLongOrDefault(String s, long defaultValue) {
        if (s == null) {
            return defaultValue;
        }
        String t = s.trim();
        if (t.isEmpty()) {
            return defaultValue;
        }
        return Long.parseLong(t);
    }
}
