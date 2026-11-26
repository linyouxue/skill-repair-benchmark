package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {

    public static final int EVENT_SUBMIT = 0;

    public long timestamp;
    public long jobId;
    public long taskIndex;
    public int eventType;

    public TaskEvent() {}

    public TaskEvent(long timestamp, long jobId, long taskIndex, int eventType) {
        this.timestamp = timestamp;
        this.jobId = jobId;
        this.taskIndex = taskIndex;
        this.eventType = eventType;
    }

    public long getTimestamp() {
        return timestamp;
    }

    public long getJobId() {
        return jobId;
    }

    public long getTaskIndex() {
        return taskIndex;
    }

    public int getEventType() {
        return eventType;
    }

    public static TaskEvent fromCsvLine(String line) {
        String[] parts = line.split(",", -1);
        if (parts.length < 6) {
            throw new IllegalArgumentException("Invalid task event line: " + line);
        }
        long timestamp = Long.parseLong(parts[0]);
        long jobId = Long.parseLong(parts[2]);
        long taskIndex = parts[3].isEmpty() ? -1L : Long.parseLong(parts[3]);
        int eventType = Integer.parseInt(parts[5]);
        return new TaskEvent(timestamp, jobId, taskIndex, eventType);
    }
}
