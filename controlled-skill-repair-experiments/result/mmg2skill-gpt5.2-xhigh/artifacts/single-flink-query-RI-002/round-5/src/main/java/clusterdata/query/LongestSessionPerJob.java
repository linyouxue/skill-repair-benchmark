package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.zip.GZIPInputStream;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
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
import org.apache.flink.util.Collector;

public class LongestSessionPerJob extends AppBase {

    private static final int TASK_EVENT_TYPE_SUBMIT = 0;

    public static void main(String[] args) throws Exception {
        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        final int sesssize = params.getInt("sesssize", 600);

        System.out.println("task_input  " + taskInput);
        System.out.println("job_input  " + jobInput);

        if (taskInput == null || jobInput == null || outputPath == null) {
            throw new IllegalArgumentException("Required parameters: --task_input --job_input --output");
        }

        long sessionGapMs = sesssize * 1000L;

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);

        SingleOutputStreamOperator<TaskEvent> taskEventsStream =
                env.addSource(taskSourceOrTest(new GzipTaskEventSource(taskInput)))
                        .name("task-events")
                        .setParallelism(1);

        SingleOutputStreamOperator<JobEvent> jobEventsStream =
                env.addSource(jobSourceOrTest(new GzipJobEventSource(jobInput)))
                        .name("job-events")
                        .setParallelism(1);

        DataStream<TaskEvent> taskEvents =
                taskEventsStream
                        .assignTimestampsAndWatermarks(
                                WatermarkStrategy.<TaskEvent>forMonotonousTimestamps()
                                        .withTimestampAssigner((e, ts) -> e.timestamp))
                        .filter(e -> e.eventType == TASK_EVENT_TYPE_SUBMIT);

        DataStream<JobEvent> jobEvents =
                jobEventsStream
                        .assignTimestampsAndWatermarks(
                                WatermarkStrategy.<JobEvent>forMonotonousTimestamps()
                                        .withTimestampAssigner((e, ts) -> e.timestamp))
                        .filter(e -> isTerminalJobEventType(e.eventType));

        DataStream<Tuple2<Long, Long>> longestStagePerJob =
                taskEvents
                        .keyBy(TaskEvent::getJobId)
                        .connect(jobEvents.keyBy(JobEvent::getJobId))
                        .process(new LongestStagePerJob(sessionGapMs));

        DataStream<String> formatted =
                longestStagePerJob.map(v -> String.format("(%d,%d)", v.f0, v.f1));

        @SuppressWarnings("unchecked")
        SinkFunction<String> sink = (SinkFunction<String>) sinkOrTest(new LocalTextFileSink(outputPath));
        formatted.addSink(sink).name("output").setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    private static boolean isTerminalJobEventType(int eventType) {
        return eventType == 3 || eventType == 4 || eventType == 5 || eventType == 6;
    }

    private static final class LongestStagePerJob
            extends KeyedCoProcessFunction<Long, TaskEvent, JobEvent, Tuple2<Long, Long>> {

        private final long sessionGapMs;

        private transient ValueState<Long> currentStageCount;
        private transient ValueState<Long> maxStageCount;
        private transient ValueState<Long> lastSubmitTs;
        private transient ValueState<Long> sessionTimerTs;
        private transient ValueState<Long> finishTs;
        private transient ValueState<Long> finishTimerTs;

        private LongestStagePerJob(long sessionGapMs) {
            this.sessionGapMs = sessionGapMs;
        }

        @Override
        public void open(Configuration parameters) {
            currentStageCount =
                    getRuntimeContext()
                            .getState(new ValueStateDescriptor<>("currentStageCount", Long.class));
            maxStageCount =
                    getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Long.class));
            lastSubmitTs =
                    getRuntimeContext().getState(new ValueStateDescriptor<>("lastSubmitTs", Long.class));
            sessionTimerTs =
                    getRuntimeContext().getState(new ValueStateDescriptor<>("sessionTimerTs", Long.class));
            finishTs = getRuntimeContext().getState(new ValueStateDescriptor<>("finishTs", Long.class));
            finishTimerTs =
                    getRuntimeContext().getState(new ValueStateDescriptor<>("finishTimerTs", Long.class));
        }

        @Override
        public void processElement1(TaskEvent task, Context ctx, Collector<Tuple2<Long, Long>> out)
                throws Exception {
            long ts = task.timestamp;
            Long finish = finishTs.value();
            if (finish != null && ts > finish) {
                return;
            }

            Long last = lastSubmitTs.value();
            long current = valueOrZero(currentStageCount.value());
            long max = valueOrZero(maxStageCount.value());

            if (last == null) {
                current = 1L;
            } else if (ts - last >= sessionGapMs) {
                max = Math.max(max, current);
                current = 1L;
            } else {
                current++;
            }

            lastSubmitTs.update(ts);
            currentStageCount.update(current);
            maxStageCount.update(max);

            Long prevTimer = sessionTimerTs.value();
            if (prevTimer != null) {
                ctx.timerService().deleteEventTimeTimer(prevTimer);
            }
            long newTimer = ts + sessionGapMs;
            sessionTimerTs.update(newTimer);
            ctx.timerService().registerEventTimeTimer(newTimer);
        }

        @Override
        public void processElement2(JobEvent job, Context ctx, Collector<Tuple2<Long, Long>> out)
                throws Exception {
            long ts = job.timestamp;
            Long existing = finishTs.value();
            if (existing == null || ts > existing) {
                finishTs.update(ts);

                Long prevTimer = finishTimerTs.value();
                if (prevTimer != null) {
                    ctx.timerService().deleteEventTimeTimer(prevTimer);
                }
                long newTimer = ts + 1L;
                finishTimerTs.update(newTimer);
                ctx.timerService().registerEventTimeTimer(newTimer);
            }
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Long>> out)
                throws Exception {
            Long finishTimer = finishTimerTs.value();
            if (finishTimer != null && timestamp == finishTimer) {
                long current = valueOrZero(currentStageCount.value());
                long max = valueOrZero(maxStageCount.value());
                out.collect(Tuple2.of(ctx.getCurrentKey(), Math.max(max, current)));

                Long sessTimer = sessionTimerTs.value();
                if (sessTimer != null) {
                    ctx.timerService().deleteEventTimeTimer(sessTimer);
                }

                currentStageCount.clear();
                maxStageCount.clear();
                lastSubmitTs.clear();
                sessionTimerTs.clear();
                finishTs.clear();
                finishTimerTs.clear();
                return;
            }

            Long sessTimer = sessionTimerTs.value();
            if (sessTimer != null && timestamp == sessTimer) {
                long current = valueOrZero(currentStageCount.value());
                long max = valueOrZero(maxStageCount.value());
                maxStageCount.update(Math.max(max, current));

                currentStageCount.clear();
                lastSubmitTs.clear();
                sessionTimerTs.clear();
            }
        }

        private static long valueOrZero(Long v) {
            return v == null ? 0L : v;
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
            try (BufferedReader reader =
                    new BufferedReader(
                            new InputStreamReader(
                                    new GZIPInputStream(new FileInputStream(path)),
                                    StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }
                    TaskEvent evt = TaskEvent.fromCsvLine(line);
                    if (evt != null) {
                        ctx.collect(evt);
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
            try (BufferedReader reader =
                    new BufferedReader(
                            new InputStreamReader(
                                    new GZIPInputStream(new FileInputStream(path)),
                                    StandardCharsets.UTF_8))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }
                    JobEvent evt = JobEvent.fromCsvLine(line);
                    if (evt != null) {
                        ctx.collect(evt);
                    }
                }
            }
        }

        @Override
        public void cancel() {
            running = false;
        }
    }

    private static final class LocalTextFileSink extends RichSinkFunction<String> {

        private final String outputPath;
        private transient java.io.BufferedWriter writer;

        private LocalTextFileSink(String outputPath) {
            this.outputPath = outputPath;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            Path path = Paths.get(outputPath);
            Path parent = path.getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }

            writer =
                    Files.newBufferedWriter(
                            path,
                            StandardCharsets.UTF_8,
                            StandardOpenOption.CREATE,
                            StandardOpenOption.TRUNCATE_EXISTING,
                            StandardOpenOption.WRITE);
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
