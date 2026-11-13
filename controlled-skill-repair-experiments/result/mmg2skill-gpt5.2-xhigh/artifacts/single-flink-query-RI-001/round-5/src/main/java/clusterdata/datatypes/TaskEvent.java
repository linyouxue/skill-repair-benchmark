package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {

    public static final int EVENT_TYPE_SUBMIT = 0;

    public long timestampMicros;
    public long jobId;
    public long taskIndex;
    public Long machineId;
    public int eventType;

    public TaskEvent() {}

    public TaskEvent(long timestampMicros, long jobId, long taskIndex, Long machineId, int eventType) {
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
        return timestampMicros / 1000L;
    }

    public long getJobId() {
        return jobId;
    }

    public long getTaskIndex() {
        return taskIndex;
    }

    public Long getMachineId() {
        return machineId;
    }

    public int getEventType() {
        return eventType;
    }

    public static TaskEvent fromCsvLine(String line) {
        String[] parts = line.split(",", -1);
        if (parts.length < 6) {
            throw new IllegalArgumentException("Invalid task event line: " + line);
        }

        long timestampMicros = Long.parseLong(parts[0]);
        long jobId = Long.parseLong(parts[2]);
        long taskIndex = Long.parseLong(parts[3]);

        Long machineId = null;
        String machine = parts[4];
        if (!machine.isEmpty()) {
            machineId = Long.parseLong(machine);
        }

        int eventType = Integer.parseInt(parts[5]);
        return new TaskEvent(timestampMicros, jobId, taskIndex, machineId, eventType);
    }
}
