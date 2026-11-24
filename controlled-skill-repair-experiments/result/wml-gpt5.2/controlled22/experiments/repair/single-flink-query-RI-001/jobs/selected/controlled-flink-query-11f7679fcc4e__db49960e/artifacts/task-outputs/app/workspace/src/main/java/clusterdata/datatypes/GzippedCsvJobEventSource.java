package clusterdata.datatypes;

import org.apache.flink.streaming.api.functions.source.SourceFunction;

import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.zip.GZIPInputStream;

public class GzippedCsvJobEventSource implements SourceFunction<JobEvent> {

    private final String path;
    private volatile boolean running = true;

    public GzippedCsvJobEventSource(String path) {
        this.path = path;
    }

    @Override
    public void run(SourceContext<JobEvent> ctx) throws Exception {
        try (InputStream fileStream = new FileInputStream(path);
             InputStream in = path != null && path.endsWith(".gz") ? new GZIPInputStream(fileStream) : fileStream;
             BufferedReader br = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {

            String line;
            while (running && (line = br.readLine()) != null) {
                JobEvent evt;
                try {
                    evt = JobEvent.fromCsvLine(line);
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
