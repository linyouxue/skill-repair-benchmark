package clusterdata.utils;

import clusterdata.datatypes.TaskEvent;
import org.apache.flink.streaming.api.functions.source.SourceFunction;

import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.zip.GZIPInputStream;

public class CsvGzTaskEventSource implements SourceFunction<TaskEvent> {
    private final String path;
    private volatile boolean running = true;

    public CsvGzTaskEventSource(String path) {
        this.path = path;
    }

    @Override
    public void run(SourceContext<TaskEvent> ctx) throws Exception {
        InputStream raw = new FileInputStream(path);
        InputStream input = path.endsWith(".gz") ? new GZIPInputStream(raw) : raw;

        try (BufferedReader reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))) {
            String line;
            while (running && (line = reader.readLine()) != null) {
                TaskEvent event = TaskEvent.fromCsvLine(line);
                if (event == null) {
                    continue;
                }
                synchronized (ctx.getCheckpointLock()) {
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
