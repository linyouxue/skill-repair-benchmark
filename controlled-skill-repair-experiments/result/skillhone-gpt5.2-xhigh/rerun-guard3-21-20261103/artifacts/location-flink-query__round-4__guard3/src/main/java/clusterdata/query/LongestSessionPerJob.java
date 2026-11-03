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
import org.apache.flink.streaming.api.windowing.assigners.EventTimeSessionWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.util.Collector;

import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.time.Duration;
import java.util.Objects;

public class LongestSessionPerJob extends AppBase {

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        final int sesssize = params.getInt("sesssize", 600);

        if ((taskInput == null || jobInput == null || outputPath == null) && AppBase.out == null) {
            throw new IllegalArgumentException("Missing required parameters: --task_input, --job_input, --output");
        }

        long sessionGapMillis = sesssize * 1_000L;

        // set up streaming execution environment
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.getConfig().setGlobalJobParameters(params);

        DataStream<TaskEvent> taskEventsStream;
        if (AppBase.taskEvents == null) {
            taskEventsStream = env.readTextFile(taskInput)
                    .map(TaskEvent::fromCsvLine)
                    .returns(TaskEvent.class)
                    .filter(Objects::nonNull)
                    .name("task-events-file");
        } else {
            taskEventsStream = env.addSource(AppBase.taskEvents).name("task-events-test");
        }

        WatermarkStrategy<TaskEvent> taskWms = WatermarkStrategy
                .<TaskEvent>forBoundedOutOfOrderness(Duration.ofMinutes(1))
                .withTimestampAssigner((event, ts) -> event.getTimestampMillis());

        DataStream<TaskEvent> taskEvents = taskEventsStream.assignTimestampsAndWatermarks(taskWms);

        DataStream<JobEvent> jobEventsStream;
        if (AppBase.jobEvents == null) {
            jobEventsStream = env.readTextFile(jobInput)
                    .map(JobEvent::fromCsvLine)
                    .returns(JobEvent.class)
                    .filter(Objects::nonNull)
                    .name("job-events-file");
        } else {
            jobEventsStream = env.addSource(AppBase.jobEvents).name("job-events-test");
        }

        WatermarkStrategy<JobEvent> jobWms = WatermarkStrategy
                .<JobEvent>forBoundedOutOfOrderness(Duration.ofMinutes(1))
                .withTimestampAssigner((event, ts) -> event.getTimestampMillis());

        DataStream<JobEvent> jobEvents = jobEventsStream.assignTimestampsAndWatermarks(jobWms);

        DataStream<Tuple2<Long, Integer>> stageCounts = taskEvents
                .filter(TaskEvent::isSubmitEvent)
                .map((MapFunction<TaskEvent, Tuple2<Long, Integer>>) value -> Tuple2.of(value.getJobId(), 1))
                .returns(Types.TUPLE(Types.LONG, Types.INT))
                .keyBy(value -> value.f0)
                .window(EventTimeSessionWindows.withGap(Time.milliseconds(sessionGapMillis)))
                .reduce((a, b) -> Tuple2.of(a.f0, a.f1 + b.f1))
                .name("stage-counts");

        DataStream<JobEvent> terminalJobEvents = jobEvents
                .filter(JobEvent::isTerminalEvent)
                .name("terminal-jobs");

        DataStream<Tuple2<Long, Integer>> longestStagePerJob = stageCounts
                .connect(terminalJobEvents)
                .keyBy(value -> value.f0, JobEvent::getJobId)
                .process(new EmitLongestStageOnFinish(sessionGapMillis))
                .name("longest-stage-per-job");

        DataStream<String> formatted = longestStagePerJob
                .map(value -> "(" + value.f0 + "," + value.f1 + ")")
                .returns(Types.STRING)
                .name("format-output");

        @SuppressWarnings("unchecked")
        SinkFunction<String> sink = (SinkFunction<String>) sinkOrTest(new LocalFileSink(outputPath));
        formatted.addSink(sink).setParallelism(1).name("output-sink");

        env.execute("LongestSessionPerJob");
    }

    private static class EmitLongestStageOnFinish
            extends KeyedCoProcessFunction<Long, Tuple2<Long, Integer>, JobEvent, Tuple2<Long, Integer>> {

        private final long sessionGapMillis;

        private transient ValueState<Integer> maxStageCount;
        private transient ValueState<Boolean> finished;
        private transient ValueState<Long> finishTimerTs;

        private EmitLongestStageOnFinish(long sessionGapMillis) {
            this.sessionGapMillis = sessionGapMillis;
        }

        @Override
        public void open(Configuration parameters) {
            maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Types.INT));
            finished = getRuntimeContext().getState(new ValueStateDescriptor<>("finished", Types.BOOLEAN));
            finishTimerTs = getRuntimeContext().getState(new ValueStateDescriptor<>("finishTimerTs", Types.LONG));
        }

        @Override
        public void processElement1(
                Tuple2<Long, Integer> value,
                Context ctx,
                Collector<Tuple2<Long, Integer>> out) throws Exception {
            Integer currentMax = maxStageCount.value();
            int candidate = value.f1 == null ? 0 : value.f1;
            if (currentMax == null || candidate > currentMax) {
                maxStageCount.update(candidate);
            }
        }

        @Override
        public void processElement2(
                JobEvent value,
                Context ctx,
                Collector<Tuple2<Long, Integer>> out) throws Exception {
            finished.update(true);

            long newTimerTs = value.getTimestampMillis() + sessionGapMillis;
            Long currentTimerTs = finishTimerTs.value();
            if (currentTimerTs != null) {
                if (newTimerTs <= currentTimerTs) {
                    return;
                }
                ctx.timerService().deleteEventTimeTimer(currentTimerTs);
            }

            ctx.timerService().registerEventTimeTimer(newTimerTs);
            finishTimerTs.update(newTimerTs);
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Integer>> out) throws Exception {
            Long expectedTimer = finishTimerTs.value();
            if (expectedTimer == null || expectedTimer != timestamp) {
                return;
            }

            Boolean isFinished = finished.value();
            if (isFinished == null || !isFinished) {
                return;
            }

            Integer max = maxStageCount.value();
            out.collect(Tuple2.of(ctx.getCurrentKey(), max == null ? 0 : max));

            maxStageCount.clear();
            finished.clear();
            finishTimerTs.clear();
        }
    }

    private static class LocalFileSink extends RichSinkFunction<String> {

        private final String outputPath;
        private transient BufferedWriter writer;

        private LocalFileSink(String outputPath) {
            this.outputPath = outputPath;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            if (outputPath == null) {
                throw new IllegalArgumentException("Output path is null");
            }

            Path path = Paths.get(outputPath);
            Path parent = path.getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }

            writer = Files.newBufferedWriter(
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
