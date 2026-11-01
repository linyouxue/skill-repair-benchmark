package clusterdata.utils;

import clusterdata.datatypes.JobEvent;
import org.apache.flink.streaming.api.functions.source.SourceFunction;

import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.zip.GZIPInputStream;

public class CsvGzJobEventSource implements SourceFunction<JobEvent> {
    private final String path;
    private volatile boolean running = true;

    public CsvGzJobEventSource(String path) {
        this.path = path;
    }

    @Override
    public void run(SourceContext<JobEvent> ctx) throws Exception {
        InputStream raw = new FileInputStream(path);
        InputStream input = path.endsWith(".gz") ? new GZIPInputStream(raw) : raw;

        try (BufferedReader reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))) {
            String line;
            while (running && (line = reader.readLine()) != null) {
                JobEvent event = JobEvent.fromCsvLine(line);
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
