package clusterdata.utils;

import clusterdata.datatypes.TaskEvent;
import org.apache.flink.streaming.api.functions.source.SourceFunction;

import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.zip.GZIPInputStream;

public class TaskEventSource implements SourceFunction<TaskEvent> {

    private final String path;
    private volatile boolean running = true;

    public TaskEventSource(String path) {
        this.path = path;
    }

    @Override
    public void run(SourceContext<TaskEvent> ctx) throws Exception {
        try (InputStream fileIn = new FileInputStream(path);
             InputStream in = path.endsWith(".gz") ? new GZIPInputStream(fileIn) : fileIn;
             BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {

            String line;
            while (running && (line = reader.readLine()) != null) {
                if (!line.isEmpty()) {
                    ctx.collect(TaskEvent.fromCsv(line));
                }
            }
        }
    }

    @Override
    public void cancel() {
        running = false;
    }
}
