package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {
    public long timestampUs;
    public long timestampMs;
    public long jobId;
    public int eventType;

    public JobEvent() {}

    public JobEvent(long timestampUs, long jobId, int eventType) {
        this.timestampUs = timestampUs;
        this.timestampMs = timestampUs / 1000L;
        this.jobId = jobId;
        this.eventType = eventType;
    }

    public static JobEvent fromCsvLine(String line) {
        if (line == null || line.isEmpty()) {
            return null;
        }

        String[] parts = line.split(",", -1);
        if (parts.length < 4) {
            return null;
        }

        long timestampUs = Long.parseLong(parts[0]);
        long jobId = Long.parseLong(parts[2]);
        int eventType = Integer.parseInt(parts[3]);

        return new JobEvent(timestampUs, jobId, eventType);
    }
}
