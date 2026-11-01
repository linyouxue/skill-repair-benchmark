package clusterdata.utils;

import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;

import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;

public class LocalTextFileSink<T> extends RichSinkFunction<T> {
    private final String outputPath;
    private transient BufferedWriter writer;

    public LocalTextFileSink(String outputPath) {
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
                StandardOpenOption.TRUNCATE_EXISTING,
                StandardOpenOption.WRITE);
    }

    @Override
    public void invoke(T value, Context context) throws Exception {
        writer.write(String.valueOf(value));
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
