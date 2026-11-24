package clusterdata.utils;

import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;

import java.io.BufferedWriter;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

public class LocalFileSink extends RichSinkFunction<String> {

    private final String path;
    private transient BufferedWriter writer;

    public LocalFileSink(String path) {
        this.path = path;
    }

    @Override
    public void open(Configuration parameters) throws Exception {
        super.open(parameters);
        Path p = Paths.get(path);
        Path parent = p.getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        this.writer = new BufferedWriter(
                new OutputStreamWriter(new FileOutputStream(path, false), StandardCharsets.UTF_8));
    }

    @Override
    public synchronized void invoke(String value, Context context) throws Exception {
        writer.write(value);
        writer.newLine();
    }

    @Override
    public synchronized void close() throws Exception {
        if (writer != null) {
            writer.flush();
            writer.close();
        }
        super.close();
    }
}
