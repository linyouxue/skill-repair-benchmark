package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {

    public static final int EVENT_SUBMIT = 0;

    public long timestampMs;
    public long jobId;
    public int eventType;

    public TaskEvent() {}

    public TaskEvent(long timestampMs, long jobId, int eventType) {
        this.timestampMs = timestampMs;
        this.jobId = jobId;
        this.eventType = eventType;
    }

    public static TaskEvent fromCsvLine(String line) {
        String[] parts = line.split(",", -1);
        long timestampUs = Long.parseLong(parts[0]);
        long jobId = Long.parseLong(parts[2]);
        int eventType = Integer.parseInt(parts[5]);
        return new TaskEvent(timestampUs / 1000L, jobId, eventType);
    }
}
