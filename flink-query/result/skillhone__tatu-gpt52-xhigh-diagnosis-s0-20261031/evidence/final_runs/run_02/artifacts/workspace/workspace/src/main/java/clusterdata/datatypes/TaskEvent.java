package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {

    public static final int EVENT_SUBMIT = 0;

    public long timestamp; // microseconds
    public long jobId;
    public long taskIndex;
    public long machineId;
    public int eventType;

    public TaskEvent() {}

    public TaskEvent(long timestamp, long jobId, long taskIndex, long machineId, int eventType) {
        this.timestamp = timestamp;
        this.jobId = jobId;
        this.taskIndex = taskIndex;
        this.machineId = machineId;
        this.eventType = eventType;
    }

    public long timestampMillis() {
        return timestamp / 1000L;
    }

    public static TaskEvent fromCsvLine(String line) {
        String[] parts = line.split(",", -1);
        // Schema (v2.1):
        // 0 time, 1 missing info, 2 job id, 3 task index, 4 machine id, 5 event type, ...
        long ts = parseLong(parts, 0, 0L);
        long jobId = parseLong(parts, 2, -1L);
        long taskIndex = parseLong(parts, 3, -1L);
        long machineId = parseLong(parts, 4, -1L);
        int eventType = (int) parseLong(parts, 5, -1L);
        return new TaskEvent(ts, jobId, taskIndex, machineId, eventType);
    }

    private static long parseLong(String[] parts, int idx, long defaultVal) {
        if (idx >= parts.length) {
            return defaultVal;
        }
        String s = parts[idx];
        if (s == null || s.isEmpty()) {
            return defaultVal;
        }
        return Long.parseLong(s);
    }
}
