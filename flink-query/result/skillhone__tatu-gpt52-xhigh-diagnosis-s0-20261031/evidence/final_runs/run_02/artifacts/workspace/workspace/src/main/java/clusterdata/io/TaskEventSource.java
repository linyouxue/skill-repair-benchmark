package clusterdata.io;

import clusterdata.datatypes.TaskEvent;
import org.apache.flink.streaming.api.functions.source.SourceFunction;
import org.apache.flink.streaming.api.watermark.Watermark;

import java.io.BufferedReader;
import java.io.FileInputStream;
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
        long lastEmittedWatermark = Long.MIN_VALUE;
        try (BufferedReader br =
                     new BufferedReader(new InputStreamReader(new GZIPInputStream(new FileInputStream(path)), StandardCharsets.UTF_8))) {
            String line;
            while (running && (line = br.readLine()) != null) {
                if (line.isEmpty()) {
                    continue;
                }

                TaskEvent event = TaskEvent.fromCsvLine(line);
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
