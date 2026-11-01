package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {
    public long timestampUs;
    public long timestampMs;
    public long jobId;
    public long taskIndex;
    public int eventType;

    public TaskEvent() {}

    public TaskEvent(long timestampUs, long jobId, long taskIndex, int eventType) {
        this.timestampUs = timestampUs;
        this.timestampMs = timestampUs / 1000L;
        this.jobId = jobId;
        this.taskIndex = taskIndex;
        this.eventType = eventType;
    }

    public static TaskEvent fromCsvLine(String line) {
        if (line == null || line.isEmpty()) {
            return null;
        }

        String[] parts = line.split(",", -1);
        if (parts.length < 6) {
            return null;
        }

        long timestampUs = Long.parseLong(parts[0]);
        long jobId = Long.parseLong(parts[2]);
        long taskIndex = parts[3].isEmpty() ? -1L : Long.parseLong(parts[3]);
        int eventType = Integer.parseInt(parts[5]);

        return new TaskEvent(timestampUs, jobId, taskIndex, eventType);
    }
}
