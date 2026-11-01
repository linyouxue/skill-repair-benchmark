package clusterdata.io;

import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;

public class Tuple2TextFileSink extends RichSinkFunction<Tuple2<Long, Long>> {

    private final String outputPath;
    private transient BufferedWriter writer;

    public Tuple2TextFileSink(String outputPath) {
        this.outputPath = outputPath;
    }

    @Override
    public void open(Configuration parameters) throws Exception {
        File outFile = new File(outputPath);
        File parent = outFile.getParentFile();
        if (parent != null && !parent.exists()) {
            //noinspection ResultOfMethodCallIgnored
            parent.mkdirs();
        }
        writer = new BufferedWriter(
                new OutputStreamWriter(new FileOutputStream(outFile, false), StandardCharsets.UTF_8));
    }

    @Override
    public void invoke(Tuple2<Long, Long> value, Context context) throws Exception {
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
