package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {
    public static final int EVENT_SUBMIT = 0;

    public long timestampUs;
    public long jobId;
    public long taskIndex;
    public int eventType;

    public TaskEvent() {}

    public TaskEvent(long timestampUs, long jobId, long taskIndex, int eventType) {
        this.timestampUs = timestampUs;
        this.jobId = jobId;
        this.taskIndex = taskIndex;
        this.eventType = eventType;
    }

    public static TaskEvent fromCsvLine(String line) {
        String[] parts = line.split(",", -1);
        if (parts.length < 6) {
            return null;
        }

        long tsUs;
        long jobId;
        long taskIndex;
        int eventType;
        try {
            tsUs = Long.parseLong(parts[0]);
            jobId = Long.parseLong(parts[2]);
            taskIndex = parts[3].isEmpty() ? -1L : Long.parseLong(parts[3]);
            eventType = Integer.parseInt(parts[5]);
        } catch (NumberFormatException e) {
            return null;
        }

        return new TaskEvent(tsUs, jobId, taskIndex, eventType);
    }
}
