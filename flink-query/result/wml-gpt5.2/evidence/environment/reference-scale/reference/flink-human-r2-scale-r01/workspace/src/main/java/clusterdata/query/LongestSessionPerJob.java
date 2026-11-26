package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.datastream.ConnectedStreams;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.streaming.api.functions.source.SourceFunction;
import org.apache.flink.util.Collector;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.zip.GZIPInputStream;

public class LongestSessionPerJob extends AppBase {

    private static final long MICROS_PER_SECOND = 1_000_000L;

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        System.out.println("task_input  " + taskInput);
        System.out.println("job_input  " + jobInput);

        final int sesssize = params.getInt("sesssize", 600);
        final long inactivityGapMicros = sesssize * MICROS_PER_SECOND;

        if (taskInput == null || jobInput == null || outputPath == null) {
            throw new IllegalArgumentException("Required parameters: task_input, job_input, output");
        }

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);

        WatermarkStrategy<TaskEvent> taskWms = WatermarkStrategy
                .<TaskEvent>forMonotonousTimestamps()
                .withTimestampAssigner((event, previousTimestamp) -> event.timestamp / 1000L);

        WatermarkStrategy<JobEvent> jobWms = WatermarkStrategy
                .<JobEvent>forMonotonousTimestamps()
                .withTimestampAssigner((event, previousTimestamp) -> event.timestamp / 1000L);

        DataStream<TaskEvent> taskStream = env
                .addSource(taskSourceOrTest(new TaskEventCsvGzSource(taskInput)), "task-events")
                .assignTimestampsAndWatermarks(taskWms);

        DataStream<JobEvent> jobStream = env
                .addSource(jobSourceOrTest(new JobEventCsvGzSource(jobInput)), "job-events")
                .assignTimestampsAndWatermarks(jobWms);

        ConnectedStreams<TaskEvent, JobEvent> connected = taskStream
                .keyBy(t -> t.jobId)
                .connect(jobStream.keyBy(j -> j.jobId));

        DataStream<Tuple2<Long, Long>> result = connected.process(new LongestStageAfterFinish(inactivityGapMicros));

        result
                .addSink((org.apache.flink.streaming.api.functions.sink.SinkFunction<Tuple2<Long, Long>>) sinkOrTest(
                        new Tuple2FileSink(outputPath)))
                .name("output")
                .setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

    public static final class TaskEventCsvGzSource implements SourceFunction<TaskEvent> {

        private final String path;
        private volatile boolean running = true;

        public TaskEventCsvGzSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<TaskEvent> ctx) throws Exception {
            try (FileInputStream fin = new FileInputStream(path);
                 GZIPInputStream gz = new GZIPInputStream(fin);
                 BufferedReader reader = new BufferedReader(new InputStreamReader(gz, StandardCharsets.UTF_8))) {

                String line;
                while (running && (line = reader.readLine()) != null) {
                    TaskEvent event = TaskEvent.fromCsvLine(line);
                    if (event != null) {
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

    public static final class JobEventCsvGzSource implements SourceFunction<JobEvent> {

        private final String path;
        private volatile boolean running = true;

        public JobEventCsvGzSource(String path) {
            this.path = path;
        }

        @Override
        public void run(SourceContext<JobEvent> ctx) throws Exception {
            try (FileInputStream fin = new FileInputStream(path);
                 GZIPInputStream gz = new GZIPInputStream(fin);
                 BufferedReader reader = new BufferedReader(new InputStreamReader(gz, StandardCharsets.UTF_8))) {

                String line;
                while (running && (line = reader.readLine()) != null) {
                    JobEvent event = JobEvent.fromCsvLine(line);
                    if (event != null) {
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

    public static final class LongestStageAfterFinish
            extends KeyedCoProcessFunction<Long, TaskEvent, JobEvent, Tuple2<Long, Long>> {

        private final long inactivityGapMicros;

        private transient ValueState<Long> lastSubmitTsMicros;
        private transient ValueState<Long> currentStageCount;
        private transient ValueState<Long> maxStageCount;

        private transient ValueState<Long> finishTsMs;

        public LongestStageAfterFinish(long inactivityGapMicros) {
            this.inactivityGapMicros = inactivityGapMicros;
        }

        @Override
        public void open(Configuration parameters) {
            lastSubmitTsMicros = getRuntimeContext().getState(
                    new ValueStateDescriptor<>("lastSubmitTsMicros", Long.class));
            currentStageCount = getRuntimeContext().getState(
                    new ValueStateDescriptor<>("currentStageCount", Long.class));
            maxStageCount = getRuntimeContext().getState(
                    new ValueStateDescriptor<>("maxStageCount", Long.class));
            finishTsMs = getRuntimeContext().getState(
                    new ValueStateDescriptor<>("finishTsMs", Long.class));
        }

        @Override
        public void processElement1(TaskEvent event, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            if (event == null || !event.isSubmit()) {
                return;
            }

            Long last = lastSubmitTsMicros.value();
            long current = currentStageCount.value() == null ? 0L : currentStageCount.value();
            long max = maxStageCount.value() == null ? 0L : maxStageCount.value();

            if (last == null) {
                current = 1L;
            } else {
                long gap = event.timestamp - last;
                if (gap > inactivityGapMicros) {
                    if (current > max) {
                        max = current;
                    }
                    current = 1L;
                } else {
                    current += 1L;
                }
            }

            lastSubmitTsMicros.update(event.timestamp);
            currentStageCount.update(current);
            maxStageCount.update(max);
        }

        @Override
        public void processElement2(JobEvent event, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            if (event == null || !event.isFinish()) {
                return;
            }

            long tsMs = event.timestamp / 1000L;
            finishTsMs.update(tsMs);
            ctx.timerService().registerEventTimeTimer(tsMs);
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
            Long finishMs = finishTsMs.value();
            if (finishMs == null || timestamp != finishMs) {
                return;
            }

            long current = currentStageCount.value() == null ? 0L : currentStageCount.value();
            long max = maxStageCount.value() == null ? 0L : maxStageCount.value();
            long longestStage = Math.max(current, max);

            if (longestStage > 0L) {
                out.collect(new Tuple2<>(ctx.getCurrentKey(), longestStage));
            }

            lastSubmitTsMicros.clear();
            currentStageCount.clear();
            maxStageCount.clear();
            finishTsMs.clear();
        }
    }

    public static final class Tuple2FileSink extends RichSinkFunction<Tuple2<Long, Long>> {

        private final String outputPath;
        private transient BufferedWriter writer;

        public Tuple2FileSink(String outputPath) {
            this.outputPath = outputPath;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            Path path = Paths.get(outputPath);
            Path parent = path.getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }

            writer = Files.newBufferedWriter(
                    path,
                    StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE,
                    StandardOpenOption.TRUNCATE_EXISTING);
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
        }
    }
}
