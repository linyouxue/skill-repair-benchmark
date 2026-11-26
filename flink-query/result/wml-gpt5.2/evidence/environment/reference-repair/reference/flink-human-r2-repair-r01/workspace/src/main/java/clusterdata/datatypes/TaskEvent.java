package clusterdata.datatypes;

import java.io.Serializable;

/**
 * Minimal TaskEvent representation for Google cluster traces task_events table.
 */
public class TaskEvent implements Serializable {

    public static final int EVENT_SUBMIT = 0;
    public static final int EVENT_SCHEDULE = 1;
    public static final int EVENT_EVICT = 2;
    public static final int EVENT_FAIL = 3;
    public static final int EVENT_FINISH = 4;
    public static final int EVENT_KILL = 5;
    public static final int EVENT_UPDATE_RUNNING = 8;

    public long timestamp;
    public long jobId;
    public int taskIndex;
    public int eventType;

    // Flink POJO requires a public no-arg constructor.
    public TaskEvent() {
    }

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
        if (line == null || line.isEmpty()) {
            return null;
        }
        String[] parts = line.split(",", -1);
        if (parts.length < 6) {
            return null;
        }
        long timestamp = parseLong(parts[0]);
        long jobId = parseLong(parts[2]);
        int taskIndex = parseInt(parts[3]);
        int eventType = parseInt(parts[5]);
        return new TaskEvent(timestamp, jobId, taskIndex, eventType);
    }

    private static long parseLong(String s) {
        if (s == null || s.isEmpty()) {
            return 0L;
        }
        return Long.parseLong(s);
    }

    private static int parseInt(String s) {
        if (s == null || s.isEmpty()) {
            return 0;
        }
        return Integer.parseInt(s);
    }
}
