package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import clusterdata.io.JobEventSource;
import clusterdata.io.TaskEventSource;
import clusterdata.io.Tuple2TextFileSink;
import clusterdata.utils.AppBase;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.datastream.SingleOutputStreamOperator;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.sink.SinkFunction;

public class LongestSessionPerJob extends AppBase {

    public static void main(String[] args) throws Exception {

        ParameterTool params = ParameterTool.fromArgs(args);
        String taskInput = params.get("task_input", null);
        String jobInput = params.get("job_input", null);
        String outputPath = params.get("output", null);
        final int sesssizeSeconds = params.getInt("sesssize", 600);

        if (taskInput == null || jobInput == null || outputPath == null) {
            throw new IllegalArgumentException("Required parameters: --task_input, --job_input, --output");
        }

        long sessionGapMillis = sesssizeSeconds * 1000L;

        // set up streaming execution environment
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        DataStream<TaskEvent> tasks = env.addSource(taskSourceOrTest(new TaskEventSource(taskInput)));
        DataStream<JobEvent> jobs = env.addSource(jobSourceOrTest(new JobEventSource(jobInput)));

        SingleOutputStreamOperator<Tuple2<Long, Long>> longestStagePerJob = tasks
                .keyBy(e -> e.jobId)
                .connect(jobs.keyBy(e -> e.jobId))
                .process(new LongestStageProcessFunction(sessionGapMillis));

        @SuppressWarnings("unchecked")
        SinkFunction<Tuple2<Long, Long>> sink = (SinkFunction<Tuple2<Long, Long>>) sinkOrTest(new Tuple2TextFileSink(outputPath));
        longestStagePerJob.addSink(sink).setParallelism(1);

        env.execute("LongestSessionPerJob");
    }

}
