package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {
    public static final int EVENT_FINISH = 4;
    public static final int EVENT_KILL = 5;

    public long timestampUs;
    public long jobId;
    public int eventType;

    public JobEvent() {}

    public JobEvent(long timestampUs, long jobId, int eventType) {
        this.timestampUs = timestampUs;
        this.jobId = jobId;
        this.eventType = eventType;
    }

    public static JobEvent fromCsvLine(String line) {
        String[] parts = line.split(",", -1);
        if (parts.length < 4) {
            return null;
        }

        long tsUs;
        long jobId;
        int eventType;
        try {
            tsUs = Long.parseLong(parts[0]);
            jobId = Long.parseLong(parts[2]);
            eventType = Integer.parseInt(parts[3]);
        } catch (NumberFormatException e) {
            return null;
        }

        return new JobEvent(tsUs, jobId, eventType);
    }
}
