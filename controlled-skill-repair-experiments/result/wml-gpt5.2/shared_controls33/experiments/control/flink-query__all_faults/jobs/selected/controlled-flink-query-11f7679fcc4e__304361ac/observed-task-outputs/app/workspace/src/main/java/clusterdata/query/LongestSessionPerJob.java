package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import clusterdata.utils.JobEventFileSource;
import clusterdata.utils.LocalFileSink;
import clusterdata.utils.TaskEventFileSource;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.typeinfo.Types;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.util.Collector;

public class LongestSessionPerJob extends AppBase {

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);

        if (taskInput == null || jobInput == null || outputPath == null) {
            throw new IllegalArgumentException("Required parameters: --task_input --job_input --output");
        }

        final int sesssizeSeconds = params.getInt("sesssize", 600);
        final long sessionGapMicros = sesssizeSeconds * 1_000_000L;

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);

        WatermarkStrategy<TaskEvent> taskWms =
                WatermarkStrategy.<TaskEvent>forMonotonousTimestamps()
                        .withTimestampAssigner((e, ts) -> e.getTimestampMicros());

        WatermarkStrategy<JobEvent> jobWms =
                WatermarkStrategy.<JobEvent>forMonotonousTimestamps()
                        .withTimestampAssigner((e, ts) -> e.getTimestampMicros());

        DataStream<TaskEvent> taskEventsStream =
                env.addSource(taskSourceOrTest(new TaskEventFileSource(taskInput)))
                        .assignTimestampsAndWatermarks(taskWms);

        DataStream<JobEvent> jobEventsStream =
                env.addSource(jobSourceOrTest(new JobEventFileSource(jobInput)))
                        .assignTimestampsAndWatermarks(jobWms);

        DataStream<Tuple2<Long, Integer>> maxStageCountPerJob =
                taskEventsStream
                        .filter(e -> e.getEventType() == TaskEvent.SUBMIT)
                        .keyBy(TaskEvent::getJobId)
                        .process(new LongestStagePerJob(sessionGapMicros))
                        .returns(Types.TUPLE(Types.LONG, Types.INT));

        DataStream<Long> finishedJobs =
                jobEventsStream
                        .filter(JobEvent::isTerminalEvent)
                        .map(JobEvent::getJobId)
                        .returns(Types.LONG);

        DataStream<String> results =
                finishedJobs
                        .connect(maxStageCountPerJob)
                        .keyBy(jobId -> jobId, t -> t.f0)
                        .process(new EmitOnEnd());

        results.addSink(sinkOrTest(new LocalFileSink(outputPath)));

        env.execute("LongestSessionPerJob");
    }

    private static class LongestStagePerJob extends KeyedProcessFunction<Long, TaskEvent, Tuple2<Long, Integer>> {

        private static final long END_OF_STREAM_TIMER = Long.MAX_VALUE - 1;

        private final long sessionGapMicros;

        private transient ValueState<Long> lastSubmitMicros;
        private transient ValueState<Integer> currentStageCount;
        private transient ValueState<Integer> maxStageCount;
        private transient ValueState<Boolean> endTimerRegistered;

        private LongestStagePerJob(long sessionGapMicros) {
            this.sessionGapMicros = sessionGapMicros;
        }

        @Override
        public void open(org.apache.flink.configuration.Configuration parameters) {
            lastSubmitMicros = getRuntimeContext().getState(new ValueStateDescriptor<>("last_submit", Long.class));
            currentStageCount =
                    getRuntimeContext().getState(new ValueStateDescriptor<>("current_stage_count", Integer.class));
            maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("max_stage_count", Integer.class));
            endTimerRegistered =
                    getRuntimeContext().getState(new ValueStateDescriptor<>("end_timer_registered", Boolean.class));
        }

        @Override
        public void processElement(TaskEvent value, Context ctx, Collector<Tuple2<Long, Integer>> out) throws Exception {
            Boolean registered = endTimerRegistered.value();
            if (registered == null || !registered) {
                ctx.timerService().registerEventTimeTimer(END_OF_STREAM_TIMER);
                endTimerRegistered.update(true);
            }

            long ts = value.getTimestampMicros();
            Long prev = lastSubmitMicros.value();
            Integer curCount = currentStageCount.value();
            Integer curMax = maxStageCount.value();

            int stageCount = curCount == null ? 0 : curCount;
            int maxCount = curMax == null ? 0 : curMax;

            if (prev == null || ts - prev >= sessionGapMicros) {
                if (stageCount > maxCount) {
                    maxCount = stageCount;
                }
                stageCount = 1;
            } else {
                stageCount += 1;
            }

            lastSubmitMicros.update(ts);
            currentStageCount.update(stageCount);
            maxStageCount.update(maxCount);
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Integer>> out) throws Exception {
            int stageCount = currentStageCount.value() == null ? 0 : currentStageCount.value();
            int maxCount = maxStageCount.value() == null ? 0 : maxStageCount.value();
            if (stageCount > maxCount) {
                maxCount = stageCount;
            }

            out.collect(Tuple2.of(ctx.getCurrentKey(), maxCount));

            lastSubmitMicros.clear();
            currentStageCount.clear();
            maxStageCount.clear();
            endTimerRegistered.clear();
        }
    }

    private static class EmitOnEnd extends KeyedCoProcessFunction<Long, Long, Tuple2<Long, Integer>, String> {

        private static final long END_OF_STREAM_TIMER = Long.MAX_VALUE - 1;

        private transient ValueState<Integer> maxStageCount;
        private transient ValueState<Boolean> finished;

        @Override
        public void open(org.apache.flink.configuration.Configuration parameters) {
            maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("max_stage", Integer.class));
            finished = getRuntimeContext().getState(new ValueStateDescriptor<>("finished", Boolean.class));
        }

        @Override
        public void processElement1(Long jobId, Context ctx, Collector<String> out) throws Exception {
            finished.update(true);
            ctx.timerService().registerEventTimeTimer(END_OF_STREAM_TIMER);
        }

        @Override
        public void processElement2(Tuple2<Long, Integer> value, Context ctx, Collector<String> out) throws Exception {
            Integer cur = maxStageCount.value();
            if (cur == null || value.f1 > cur) {
                maxStageCount.update(value.f1);
            }
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<String> out) throws Exception {
            Boolean isFinished = finished.value();
            if (isFinished != null && isFinished) {
                Integer cur = maxStageCount.value();
                int count = cur == null ? 0 : cur;
                out.collect("(" + ctx.getCurrentKey() + "," + count + ")");
            }
            maxStageCount.clear();
            finished.clear();
        }
    }
}
