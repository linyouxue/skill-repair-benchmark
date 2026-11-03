package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import org.apache.flink.api.common.eventtime.SerializableTimestampAssigner;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.functions.AggregateFunction;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.streaming.api.windowing.assigners.EventTimeSessionWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;

import java.time.Duration;

public class LongestSessionPerJob extends AppBase {

    private static final long MICROS_PER_MILLI = 1_000L;

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        final int sesssize = params.getInt("sesssize", 600);

        if (taskInput == null || jobInput == null || outputPath == null) {
            throw new IllegalArgumentException("Missing required parameters: task_input, job_input, output");
        }

        // set up streaming execution environment
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.getConfig().setGlobalJobParameters(params);

        WatermarkStrategy<TaskEvent> taskWm = WatermarkStrategy
                .<TaskEvent>forBoundedOutOfOrderness(Duration.ofSeconds(0))
                .withTimestampAssigner((SerializableTimestampAssigner<TaskEvent>)
                        (event, previousTimestamp) -> event.timestamp / MICROS_PER_MILLI);

        DataStream<TaskEvent> taskEvents = env
                .readTextFile(taskInput)
                .filter(line -> line != null && !line.isEmpty())
                .map(TaskEvent::fromCsv)
                .assignTimestampsAndWatermarks(taskWm);

        DataStream<StageCount> stageCounts = taskEvents
                .filter(e -> e.eventType == TaskEvent.SUBMIT)
                .keyBy(TaskEvent::getJobId)
                .window(EventTimeSessionWindows.withGap(Time.seconds(sesssize)))
                .aggregate(new CountAgg(), new StageCountWindowFn());

        WatermarkStrategy<JobEvent> jobWm = WatermarkStrategy
                .<JobEvent>forBoundedOutOfOrderness(Duration.ofSeconds(0))
                .withTimestampAssigner((SerializableTimestampAssigner<JobEvent>)
                        (event, previousTimestamp) -> event.timestamp / MICROS_PER_MILLI);

        DataStream<JobUpdate> jobEndUpdates = env
                .readTextFile(jobInput)
                .filter(line -> line != null && !line.isEmpty())
                .map(JobEvent::fromCsv)
                .assignTimestampsAndWatermarks(jobWm)
                .filter(JobEvent::isTerminal)
                .map(e -> JobUpdate.forJobEnd(e.jobId));

        DataStream<JobUpdate> stageUpdates = stageCounts.map(JobUpdate::forStageCount);

        DataStream<String> result = stageUpdates
                .union(jobEndUpdates)
                .keyBy(u -> u.jobId)
                .process(new EmitOnEnd());

        result.writeAsText(outputPath).setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    public static class StageCount {
        public long jobId;
        public long count;

        public StageCount() {}

        public StageCount(long jobId, long count) {
            this.jobId = jobId;
            this.count = count;
        }
    }

    public static class JobUpdate {
        public long jobId;
        public Long stageCount;
        public boolean jobEnded;

        public JobUpdate() {}

        public static JobUpdate forStageCount(StageCount sc) {
            JobUpdate u = new JobUpdate();
            u.jobId = sc.jobId;
            u.stageCount = sc.count;
            u.jobEnded = false;
            return u;
        }

        public static JobUpdate forJobEnd(long jobId) {
            JobUpdate u = new JobUpdate();
            u.jobId = jobId;
            u.stageCount = null;
            u.jobEnded = true;
            return u;
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

    public static class StageCountWindowFn extends ProcessWindowFunction<Long, StageCount, Long, TimeWindow> {

        @Override
        public void process(Long jobId, Context context, Iterable<Long> elements, Collector<StageCount> out) {
            long count = elements.iterator().next();
            out.collect(new StageCount(jobId, count));
        }
    }

    public static class EmitOnEnd extends KeyedProcessFunction<Long, JobUpdate, String> {

        private ValueState<Long> maxStageCount;
        private ValueState<Boolean> jobEnded;
        private ValueState<Boolean> timerRegistered;

        @Override
        public void open(Configuration parameters) {
            maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Long.class));
            jobEnded = getRuntimeContext().getState(new ValueStateDescriptor<>("jobEnded", Boolean.class));
            timerRegistered = getRuntimeContext().getState(new ValueStateDescriptor<>("timerRegistered", Boolean.class));
        }

        @Override
        public void processElement(JobUpdate value, Context ctx, Collector<String> out) throws Exception {
            Long currentMax = maxStageCount.value();
            if (currentMax == null) {
                currentMax = 0L;
            }

            if (value.stageCount != null && value.stageCount > currentMax) {
                maxStageCount.update(value.stageCount);
            }
            if (value.jobEnded) {
                jobEnded.update(true);
            }

            Boolean registered = timerRegistered.value();
            if (registered == null || !registered) {
                // Fires once at end-of-input when MAX_WATERMARK is emitted.
                ctx.timerService().registerEventTimeTimer(Long.MAX_VALUE - 1);
                timerRegistered.update(true);
            }
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<String> out) throws Exception {
            Boolean ended = jobEnded.value();
            if (ended != null && ended) {
                Long max = maxStageCount.value();
                if (max == null) {
                    max = 0L;
                }
                long jobId = ctx.getCurrentKey();
                out.collect("(" + jobId + "," + max + ")");
            }

            maxStageCount.clear();
            jobEnded.clear();
            timerRegistered.clear();
        }
    }
}
