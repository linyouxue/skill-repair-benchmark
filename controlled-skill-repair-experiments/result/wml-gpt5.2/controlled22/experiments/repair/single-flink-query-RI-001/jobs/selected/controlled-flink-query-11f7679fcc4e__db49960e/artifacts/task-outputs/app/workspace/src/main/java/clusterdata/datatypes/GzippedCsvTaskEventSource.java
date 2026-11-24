package clusterdata.datatypes;

import org.apache.flink.streaming.api.functions.source.SourceFunction;

import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.zip.GZIPInputStream;

public class GzippedCsvTaskEventSource implements SourceFunction<TaskEvent> {

    private final String path;
    private volatile boolean running = true;

    public GzippedCsvTaskEventSource(String path) {
        this.path = path;
    }

    @Override
    public void run(SourceContext<TaskEvent> ctx) throws Exception {
        try (InputStream fileStream = new FileInputStream(path);
             InputStream in = path != null && path.endsWith(".gz") ? new GZIPInputStream(fileStream) : fileStream;
             BufferedReader br = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {

            String line;
            while (running && (line = br.readLine()) != null) {
                TaskEvent evt;
                try {
                    evt = TaskEvent.fromCsvLine(line);
                } catch (RuntimeException e) {
                    continue;
                }
                if (evt == null) {
                    continue;
                }
                synchronized (ctx.getCheckpointLock()) {
                    ctx.collect(evt);
                }
            }
        }
    }

    @Override
    public void cancel() {
        running = false;
    }
}
