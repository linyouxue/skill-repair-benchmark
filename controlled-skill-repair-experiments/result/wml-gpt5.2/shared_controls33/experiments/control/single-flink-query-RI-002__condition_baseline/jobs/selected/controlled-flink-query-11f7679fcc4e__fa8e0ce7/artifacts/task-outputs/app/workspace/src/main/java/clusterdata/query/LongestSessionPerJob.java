package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.utils.AppBase;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.streaming.api.functions.sink.SinkFunction;
import org.apache.flink.streaming.api.functions.source.RichSourceFunction;
import org.apache.flink.streaming.api.watermark.Watermark;
import org.apache.flink.util.Collector;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.Serializable;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.GZIPInputStream;

public class LongestSessionPerJob extends AppBase {

    private interface TimestampExtractor<T> extends Serializable {
        long extractTimestamp(T value);
    }

    private interface Parser<T> extends Serializable {
        T parse(String line);
    }

    private static final class GzippedCsvSource<T> extends RichSourceFunction<T> {
        private final String path;
        private final Parser<T> parser;
        private final TimestampExtractor<T> timestampExtractor;
        private volatile boolean running = true;

        private GzippedCsvSource(String path, Parser<T> parser, TimestampExtractor<T> timestampExtractor) {
            this.path = path;
            this.parser = parser;
            this.timestampExtractor = timestampExtractor;
        }

        @Override
        public void run(SourceContext<T> ctx) throws Exception {
            final Object lock = ctx.getCheckpointLock();
            long lastWatermark = Long.MIN_VALUE;

            try (InputStream fis = Files.newInputStream(Path.of(path));
                 InputStream gis = new GZIPInputStream(fis);
                 BufferedReader br = new BufferedReader(new InputStreamReader(gis, StandardCharsets.UTF_8))) {

                String line;
                while (running && (line = br.readLine()) != null) {
                    if (line.isEmpty()) {
                        continue;
                    }

                    T event = parser.parse(line);
                    long ts = timestampExtractor.extractTimestamp(event);
                    synchronized (lock) {
                        ctx.collectWithTimestamp(event, ts);
                        if (ts > lastWatermark) {
                            ctx.emitWatermark(new Watermark(ts));
                            lastWatermark = ts;
                        }
                    }
                }

                synchronized (lock) {
                    ctx.emitWatermark(new Watermark(Long.MAX_VALUE));
                }
            }
        }

        @Override
        public void cancel() {
            running = false;
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
            Path p = Path.of(path);
            Path parent = p.getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }
            writer = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(path, false), StandardCharsets.UTF_8));
        }

        @Override
        public void invoke(String value, Context context) throws Exception {
            writer.write(value);
            writer.newLine();
        }

        @Override
        public void close() throws IOException {
            if (writer != null) {
                writer.flush();
                writer.close();
            }
        }
    }

    private static final class LongestStagePerJobProcess
            extends KeyedCoProcessFunction<Long, TaskEvent, JobEvent, Tuple2<Long, Integer>> {

        private final long sessionGapMicros;

        private transient ValueState<Long> lastSubmitTs;
        private transient ValueState<Integer> currentStageCount;
        private transient ValueState<Integer> maxStageCount;

        private transient ValueState<Long> finishCandidateTs;
        private transient ValueState<Long> finishCandidateTimerTs;
        private transient ValueState<Boolean> emitted;

        private LongestStagePerJobProcess(long sessionGapMicros) {
            this.sessionGapMicros = sessionGapMicros;
        }

        @Override
        public void open(Configuration parameters) {
            lastSubmitTs = getRuntimeContext().getState(new ValueStateDescriptor<>("lastSubmitTs", Long.class));
            currentStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("currentStageCount", Integer.class));
            maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Integer.class));

            finishCandidateTs = getRuntimeContext().getState(new ValueStateDescriptor<>("finishCandidateTs", Long.class));
            finishCandidateTimerTs = getRuntimeContext().getState(new ValueStateDescriptor<>("finishCandidateTimerTs", Long.class));
            emitted = getRuntimeContext().getState(new ValueStateDescriptor<>("emitted", Boolean.class));
        }

        @Override
        public void processElement1(TaskEvent value, Context ctx, Collector<Tuple2<Long, Integer>> out) throws Exception {
            Boolean alreadyEmitted = emitted.value();
            if (alreadyEmitted != null && alreadyEmitted) {
                return;
            }

            long ts = value.timestamp;

            Long last = lastSubmitTs.value();
            Integer cur = currentStageCount.value();
            Integer max = maxStageCount.value();

            if (cur == null) {
                cur = 0;
            }
            if (max == null) {
                max = 0;
            }

            if (last != null && ts - last >= sessionGapMicros) {
                if (cur > max) {
                    max = cur;
                }
                cur = 0;
            }

            cur += 1;

            lastSubmitTs.update(ts);
            currentStageCount.update(cur);
            maxStageCount.update(max);
        }

        @Override
        public void processElement2(JobEvent value, Context ctx, Collector<Tuple2<Long, Integer>> out) throws Exception {
            Boolean alreadyEmitted = emitted.value();
            if (alreadyEmitted != null && alreadyEmitted) {
                return;
            }

            long ts = value.timestamp;

            Long candidate = finishCandidateTs.value();
            Long timerTs = finishCandidateTimerTs.value();

            if (value.isTerminal()) {
                if (candidate == null || ts > candidate) {
                    if (timerTs != null) {
                        ctx.timerService().deleteEventTimeTimer(timerTs);
                    }
                    long newTimerTs = ts + 1L;
                    finishCandidateTs.update(ts);
                    finishCandidateTimerTs.update(newTimerTs);
                    ctx.timerService().registerEventTimeTimer(newTimerTs);
                }
                return;
            }

            if (candidate != null && ts >= candidate) {
                if (timerTs != null) {
                    ctx.timerService().deleteEventTimeTimer(timerTs);
                }
                finishCandidateTs.clear();
                finishCandidateTimerTs.clear();
            }
        }

        @Override
        public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Integer>> out) throws Exception {
            Boolean alreadyEmitted = emitted.value();
            if (alreadyEmitted != null && alreadyEmitted) {
                return;
            }

            Long candidate = finishCandidateTs.value();
            Long expectedTimerTs = finishCandidateTimerTs.value();
            if (candidate == null || expectedTimerTs == null || timestamp != expectedTimerTs) {
                return;
            }

            Integer cur = currentStageCount.value();
            Integer max = maxStageCount.value();
            if (cur == null) {
                cur = 0;
            }
            if (max == null) {
                max = 0;
            }
            if (cur > max) {
                max = cur;
            }

            out.collect(Tuple2.of(ctx.getCurrentKey(), max));

            emitted.update(true);

            lastSubmitTs.clear();
            currentStageCount.clear();
            maxStageCount.clear();
            finishCandidateTs.clear();
            finishCandidateTimerTs.clear();
        }
    }

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        System.out.println("task_input  " + taskInput);
        System.out.println("job_input  " + jobInput);

        final int sesssize = params.getInt("sesssize", 600);
        final long sessionGapMicros = sesssize * 1_000_000L;

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        if (taskEvents == null && taskInput == null) {
            throw new IllegalArgumentException("task_input is required");
        }
        if (jobEvents == null && jobInput == null) {
            throw new IllegalArgumentException("job_input is required");
        }
        if (out == null && outputPath == null) {
            throw new IllegalArgumentException("output is required");
        }

        DataStream<TaskEvent> taskStream = env
                .addSource(taskSourceOrTest(new GzippedCsvSource<>(
                        taskInput,
                        TaskEvent::fromCsvLine,
                        (TimestampExtractor<TaskEvent>) e -> e.timestamp)))
                .name("task-events")
                .setParallelism(1);

        DataStream<JobEvent> jobStream = env
                .addSource(jobSourceOrTest(new GzippedCsvSource<>(
                        jobInput,
                        JobEvent::fromCsvLine,
                        (TimestampExtractor<JobEvent>) e -> e.timestamp)))
                .name("job-events")
                .setParallelism(1);

        DataStream<TaskEvent> submits = taskStream
                .filter(e -> e.eventType == TaskEvent.SUBMIT)
                .name("task-submit-events");

        DataStream<Tuple2<Long, Integer>> longestPerJob = submits
                .keyBy(TaskEvent::getJobId)
                .connect(jobStream.keyBy(JobEvent::getJobId))
                .process(new LongestStagePerJobProcess(sessionGapMicros))
                .name("longest-stage-per-job");

        DataStream<String> formatted = longestPerJob
                .map(t -> "(" + t.f0 + "," + t.f1 + ")")
                .name("format-output");

        formatted
                .addSink((SinkFunction<String>) sinkOrTest(new LocalFileSink(outputPath)))
                .name("file-sink")
                .setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

}
