package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import clusterdata.utils.CsvGzJobEventSource;
import clusterdata.utils.CsvGzTaskEventSource;
import clusterdata.utils.LocalTextFileSink;
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

    public static void main(String[] args) throws Exception {
        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        final int sesssize = params.getInt("sesssize", 600);

        System.out.println("task_input  " + taskInput);
        System.out.println("job_input  " + jobInput);

        if (taskInput == null || jobInput == null || outputPath == null) {
            throw new IllegalArgumentException("Required parameters: --task_input, --job_input, --output");
        }

        final long gapUs = sesssize * 1_000_000L;

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);

        WatermarkStrategy<TaskEvent> taskWm = WatermarkStrategy
                .<TaskEvent>forMonotonousTimestamps()
                .withTimestampAssigner((e, ts) -> e.timestampUs);

        WatermarkStrategy<JobEvent> jobWm = WatermarkStrategy
                .<JobEvent>forMonotonousTimestamps()
                .withTimestampAssigner((e, ts) -> e.timestampUs);

        DataStream<TaskEvent> tasks = env
                .addSource(taskSourceOrTest(new CsvGzTaskEventSource(taskInput)))
                .assignTimestampsAndWatermarks(taskWm);

        DataStream<JobEvent> jobTerminalEvents = env
                .addSource(jobSourceOrTest(new CsvGzJobEventSource(jobInput)))
                .assignTimestampsAndWatermarks(jobWm)
                .filter(e -> e.eventType == JobEvent.EVENT_FINISH || e.eventType == JobEvent.EVENT_KILL);

        DataStream<Tuple2<Long, Long>> longestStagePerJob = tasks
                .connect(jobTerminalEvents)
                .keyBy(e -> e.jobId, e -> e.jobId)
                .process(new LongestStageWhenJobEnds(gapUs));

        @SuppressWarnings("unchecked")
        SinkFunction<Tuple2<Long, Long>> sink = (SinkFunction<Tuple2<Long, Long>>) sinkOrTest(new LocalTextFileSink<>(outputPath));

        longestStagePerJob
                .addSink(sink)
                .setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    private static class LongestStageWhenJobEnds
            extends KeyedCoProcessFunction<Long, TaskEvent, JobEvent, Tuple2<Long, Long>> {

        private final long gapUs;

        private transient ValueState<Long> lastSubmitTsMs;
        private transient ValueState<Long> currentStageCount;
        private transient ValueState<Long> maxStageCount;
        private transient ValueState<Long> finishTimerTsMs;

        private LongestStageWhenJobEnds(long gapUs) {
            this.gapUs = gapUs;
        }

        @Override
        public void open(Configuration parameters) {
            lastSubmitTsMs = getRuntimeContext().getState(new ValueStateDescriptor<>("lastSubmitTsMs", Long.class));
            currentStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("currentStageCount", Long.class));
            maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Long.class));
            finishTimerTsMs = getRuntimeContext().getState(new ValueStateDescriptor<>("finishTimerTsMs", Long.class));
        }

        @Override
        public void processElement1(TaskEvent task, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            if (task.eventType != TaskEvent.EVENT_SUBMIT) {
                return;
            }

            long ts = task.timestampUs;

            Long lastTs = lastSubmitTsMs.value();
            Long cur = currentStageCount.value();
            Long max = maxStageCount.value();

            if (cur == null) {
                cur = 0L;
            }
            if (max == null) {
                max = 0L;
            }

            if (lastTs == null || ts - lastTs >= gapUs) {
                if (cur > max) {
                    max = cur;
                }
                cur = 1L;
            } else {
                cur = cur + 1L;
            }

            lastSubmitTsMs.update(ts);
            currentStageCount.update(cur);
            maxStageCount.update(max);
        }

        @Override
        public void processElement2(JobEvent job, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            Long existingTimer = finishTimerTsMs.value();
            if (existingTimer != null) {
                return;
            }

            long finishTs = job.timestampUs;
            finishTimerTsMs.update(finishTs);
            ctx.timerService().registerEventTimeTimer(finishTs);
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            Long finishTs = finishTimerTsMs.value();
            if (finishTs == null || finishTs != timestamp) {
                return;
            }

            Long max = maxStageCount.value();
            Long cur = currentStageCount.value();

            if (max == null) {
                max = 0L;
            }
            if (cur != null && cur > max) {
                max = cur;
            }

            out.collect(Tuple2.of(ctx.getCurrentKey(), max));

            lastSubmitTsMs.clear();
            currentStageCount.clear();
            maxStageCount.clear();
            finishTimerTsMs.clear();
        }
    }
}
