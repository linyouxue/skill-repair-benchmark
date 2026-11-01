package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    public long timestampUs;
    public long jobId;
    public int eventType;

    public JobEvent() {
    }

    public JobEvent(long timestampUs, long jobId, int eventType) {
        this.timestampUs = timestampUs;
        this.jobId = jobId;
        this.eventType = eventType;
    }

    public long timestampMs() {
        return timestampUs / 1000L;
    }

    public static JobEvent fromCsv(String line) {
        String[] parts = line.split(",", -1);
        long timestampUs = Long.parseLong(parts[0]);
        long jobId = Long.parseLong(parts[2]);
        int eventType = Integer.parseInt(parts[3]);
        return new JobEvent(timestampUs, jobId, eventType);
    }
}
