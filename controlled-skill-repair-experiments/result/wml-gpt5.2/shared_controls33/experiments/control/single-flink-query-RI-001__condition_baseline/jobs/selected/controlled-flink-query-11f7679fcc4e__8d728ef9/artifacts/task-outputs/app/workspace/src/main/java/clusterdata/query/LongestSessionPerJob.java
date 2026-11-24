package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import clusterdata.utils.JobEventSource;
import clusterdata.utils.LocalFileSink;
import clusterdata.utils.TaskEventSource;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.streaming.api.functions.sink.SinkFunction;
import org.apache.flink.util.Collector;

public class LongestSessionPerJob extends AppBase {

    private static final long MICROS_PER_SECOND = 1_000_000L;

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        System.out.println("task_input  " + taskInput);
        System.out.println("job_input  " + jobInput);


        if (taskInput == null || jobInput == null || outputPath == null) {
            throw new IllegalArgumentException("Required parameters: --task_input, --job_input, --output");
        }

        final int sesssize = params.getInt("sesssize", 600);
        final long sessionGapMicros = sesssize * MICROS_PER_SECOND;

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        DataStream<TaskEvent> taskEventsStream = env
                .addSource(taskSourceOrTest(new TaskEventSource(taskInput)))
                .name("task-events")
                .setParallelism(1)
                .assignTimestampsAndWatermarks(
                        WatermarkStrategy.<TaskEvent>forMonotonousTimestamps()
                                .withTimestampAssigner((e, ts) -> e.timestamp));

        DataStream<JobEvent> jobEventsStream = env
                .addSource(jobSourceOrTest(new JobEventSource(jobInput)))
                .name("job-events")
                .setParallelism(1)
                .assignTimestampsAndWatermarks(
                        WatermarkStrategy.<JobEvent>forMonotonousTimestamps()
                                .withTimestampAssigner((e, ts) -> e.timestamp));

        DataStream<Tuple2<Long, Integer>> perJobLongestStage = taskEventsStream
                .filter(e -> e.eventType == TaskEvent.EVENT_SUBMIT)
                .connect(jobEventsStream.filter(e -> JobEvent.isTerminal(e.eventType)))
                .keyBy(t -> t.jobId, j -> j.jobId)
                .process(new LongestStageOnFinish(sessionGapMicros))
                .name("longest-stage-per-job");

        DataStream<String> formatted = perJobLongestStage
                .map(t -> "(" + t.f0 + "," + t.f1 + ")")
                .name("format-output");

        if (out == null) {
            formatted.addSink(new LocalFileSink(outputPath)).name("output-sink").setParallelism(1);
        } else {
            perJobLongestStage.addSink((SinkFunction) out).name("test-sink").setParallelism(1);
        }

        env.execute("LongestSessionPerJob");
    }

    private static final class LongestStageOnFinish
            extends KeyedCoProcessFunction<Long, TaskEvent, JobEvent, Tuple2<Long, Integer>> {

        private final long sessionGapMicros;

        private transient ValueState<Long> lastSubmitTs;
        private transient ValueState<Integer> currentStageCount;
        private transient ValueState<Integer> maxStageCount;
        private transient ValueState<Long> finishTs;
        private transient ValueState<Boolean> sawSubmit;

        private LongestStageOnFinish(long sessionGapMicros) {
            this.sessionGapMicros = sessionGapMicros;
        }

        @Override
        public void open(Configuration parameters) {
            lastSubmitTs = getRuntimeContext().getState(new ValueStateDescriptor<>("lastSubmitTs", Long.class));
            currentStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("currentStageCount", Integer.class));
            maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Integer.class));
            finishTs = getRuntimeContext().getState(new ValueStateDescriptor<>("finishTs", Long.class));
            sawSubmit = getRuntimeContext().getState(new ValueStateDescriptor<>("sawSubmit", Boolean.class));
        }

        @Override
        public void processElement1(TaskEvent value, Context ctx, Collector<Tuple2<Long, Integer>> out) throws Exception {
            Long finishedAt = finishTs.value();
            if (finishedAt != null && value.timestamp > finishedAt) {
                return;
            }

            Long last = lastSubmitTs.value();
            Integer cur = currentStageCount.value();
            if (cur == null) {
                cur = 0;
            }

            if (last != null && (value.timestamp - last) >= sessionGapMicros) {
                updateMaxWith(cur);
                cur = 0;
            }

            cur += 1;
            currentStageCount.update(cur);
            lastSubmitTs.update(value.timestamp);
            sawSubmit.update(true);
        }

        @Override
        public void processElement2(JobEvent value, Context ctx, Collector<Tuple2<Long, Integer>> out) throws Exception {
            if (finishTs.value() != null) {
                return;
            }
            finishTs.update(value.timestamp);
            ctx.timerService().registerEventTimeTimer(value.timestamp);
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Integer>> out) throws Exception {
            Long finishedAt = finishTs.value();
            if (finishedAt == null || finishedAt != timestamp) {
                return;
            }

            Integer cur = currentStageCount.value();
            if (cur == null) {
                cur = 0;
            }
            updateMaxWith(cur);

            Integer max = maxStageCount.value();
            if (max == null) {
                max = 0;
            }

            Boolean saw = sawSubmit.value();
            int result = Boolean.TRUE.equals(saw) ? max : 0;
            out.collect(Tuple2.of(ctx.getCurrentKey(), result));

            lastSubmitTs.clear();
            currentStageCount.clear();
            maxStageCount.clear();
            finishTs.clear();
            sawSubmit.clear();
        }

        private void updateMaxWith(int candidate) throws Exception {
            Integer max = maxStageCount.value();
            if (max == null || candidate > max) {
                maxStageCount.update(candidate);
            }
        }
    }
}
