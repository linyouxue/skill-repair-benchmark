package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {

    public static final int EVENT_SUBMIT = 0;

    private final long timestampMicros;
    private final long jobId;
    private final long taskIndex;
    private final long machineId;
    private final int eventType;

    public TaskEvent(long timestampMicros, long jobId, long taskIndex, long machineId, int eventType) {
        this.timestampMicros = timestampMicros;
        this.jobId = jobId;
        this.taskIndex = taskIndex;
        this.machineId = machineId;
        this.eventType = eventType;
    }

    public long getTimestampMicros() {
        return timestampMicros;
    }

    public long getTimestampMillis() {
        return timestampMicros / 1_000L;
    }

    public long getJobId() {
        return jobId;
    }

    public long getTaskIndex() {
        return taskIndex;
    }

    public long getMachineId() {
        return machineId;
    }

    public int getEventType() {
        return eventType;
    }

    public boolean isSubmitEvent() {
        return eventType == EVENT_SUBMIT;
    }

    public static TaskEvent fromCsvLine(String line) {
        if (line == null || line.isEmpty()) {
            return null;
        }

        String[] parts = line.split(",", -1);
        if (parts.length < 6) {
            throw new IllegalArgumentException("Invalid task event line: " + line);
        }

        long timestampMicros = parseLong(parts[0], 0L);
        long jobId = parseLong(parts[2], -1L);
        long taskIndex = parseLong(parts[3], -1L);
        long machineId = parseLong(parts[4], -1L);
        int eventType = (int) parseLong(parts[5], -1L);

        return new TaskEvent(timestampMicros, jobId, taskIndex, machineId, eventType);
    }

    private static long parseLong(String value, long defaultValue) {
        if (value == null || value.isEmpty()) {
            return defaultValue;
        }
        return Long.parseLong(value);
    }
}
