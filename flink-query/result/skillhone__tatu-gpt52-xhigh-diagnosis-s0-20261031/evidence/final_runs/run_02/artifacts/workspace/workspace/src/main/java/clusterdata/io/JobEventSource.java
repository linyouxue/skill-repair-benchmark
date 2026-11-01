package clusterdata.io;

import clusterdata.datatypes.JobEvent;
import org.apache.flink.streaming.api.functions.source.SourceFunction;
import org.apache.flink.streaming.api.watermark.Watermark;

import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.zip.GZIPInputStream;

public class JobEventSource implements SourceFunction<JobEvent> {

    private final String path;
    private volatile boolean running = true;

    public JobEventSource(String path) {
        this.path = path;
    }

    @Override
    public void run(SourceContext<JobEvent> ctx) throws Exception {
        long lastEmittedWatermark = Long.MIN_VALUE;
        try (BufferedReader br =
                     new BufferedReader(new InputStreamReader(new GZIPInputStream(new FileInputStream(path)), StandardCharsets.UTF_8))) {
            String line;
            while (running && (line = br.readLine()) != null) {
                if (line.isEmpty()) {
                    continue;
                }

                JobEvent event = JobEvent.fromCsvLine(line);
                long ts = event.timestampMillis();
                long wm = ts - 1L;

                synchronized (ctx.getCheckpointLock()) {
                    ctx.collectWithTimestamp(event, ts);
                    if (wm > lastEmittedWatermark) {
                        ctx.emitWatermark(new Watermark(wm));
                        lastEmittedWatermark = wm;
                    }
                }
            }
        }

        synchronized (ctx.getCheckpointLock()) {
            ctx.emitWatermark(Watermark.MAX_WATERMARK);
        }
    }

    @Override
    public void cancel() {
        running = false;
    }
}
