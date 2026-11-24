package clusterdata.utils;

import clusterdata.datatypes.JobEvent;
import org.apache.flink.streaming.api.functions.source.SourceFunction;

import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.zip.GZIPInputStream;

public class JobEventFileSource implements SourceFunction<JobEvent> {

    private final String path;
    private volatile boolean running = true;

    public JobEventFileSource(String path) {
        this.path = path;
    }

    @Override
    public void run(SourceContext<JobEvent> ctx) throws Exception {
        try (InputStream raw = new FileInputStream(path);
             InputStream in = path.endsWith(".gz") ? new GZIPInputStream(raw) : raw;
             BufferedReader br = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {

            String line;
            final Object lock = ctx.getCheckpointLock();
            while (running && (line = br.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty()) {
                    continue;
                }
                JobEvent evt = JobEvent.fromCsvLine(line);
                synchronized (lock) {
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
