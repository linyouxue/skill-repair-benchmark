package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {

    public static final int SUBMIT = 0;
    public static final int SCHEDULE = 1;
    public static final int EVICT = 2;
    public static final int FAIL = 3;
    public static final int FINISH = 4;
    public static final int KILL = 5;

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

    public static TaskEvent fromCsv(String line) {
        if (line == null) {
            return null;
        }
        String trimmed = line.trim();
        if (trimmed.isEmpty()) {
            return null;
        }

        String[] parts = trimmed.split(",", -1);
        if (parts.length < 6) {
            return null;
        }

        try {
            long ts = Long.parseLong(parts[0]);
            long jobId = Long.parseLong(parts[2]);
            long taskIndex = Long.parseLong(parts[3]);
            int eventType = Integer.parseInt(parts[5]);
            return new TaskEvent(ts, jobId, taskIndex, eventType);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    public boolean isSubmit() {
        return eventType == SUBMIT;
    }

    public long getTimestamp() {
        return timestamp;
    }

    public long getTime() {
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

    public void setTimestamp(long timestamp) {
        this.timestamp = timestamp;
    }

    public void setTime(long timestamp) {
        this.timestamp = timestamp;
    }

    public void setJobId(long jobId) {
        this.jobId = jobId;
    }

    public void setTaskIndex(long taskIndex) {
        this.taskIndex = taskIndex;
    }

    public void setEventType(int eventType) {
        this.eventType = eventType;
    }
}
