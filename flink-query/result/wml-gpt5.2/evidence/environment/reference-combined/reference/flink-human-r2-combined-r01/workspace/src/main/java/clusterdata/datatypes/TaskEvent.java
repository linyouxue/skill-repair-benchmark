package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {
    public static final int EVENT_SUBMIT = 0;

    public long timestamp;
    public long jobId;
    public int taskIndex;
    public int eventType;

    public TaskEvent() {}

    public TaskEvent(long timestamp, long jobId, int taskIndex, int eventType) {
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

    public int getTaskIndex() {
        return taskIndex;
    }

    public int getEventType() {
        return eventType;
    }

    public boolean isSubmit() {
        return eventType == EVENT_SUBMIT;
    }

    public static TaskEvent fromCsvLine(String line) {
        String[] parts = line.split(",", -1);
        long ts = Long.parseLong(parts[0]);
        long jobId = Long.parseLong(parts[2]);
        int taskIndex = Integer.parseInt(parts[3]);
        int eventType = Integer.parseInt(parts[5]);
        return new TaskEvent(ts, jobId, taskIndex, eventType);
    }
}
