package clusterdata.datatypes;

public class TaskEvent {

    public static final int EVENT_SUBMIT = 0;

    public long timestampMs;
    public long jobId;
    public int taskIndex;
    public long machineId;
    public int eventType;

    public TaskEvent() {}

    public TaskEvent(long timestampMs, long jobId, int taskIndex, long machineId, int eventType) {
        this.timestampMs = timestampMs;
        this.jobId = jobId;
        this.taskIndex = taskIndex;
        this.machineId = machineId;
        this.eventType = eventType;
    }

    public static TaskEvent fromCsvLine(String line) {
        if (line == null) {
            return null;
        }

        String[] parts = line.split(",", -1);
        if (parts.length < 6) {
            return null;
        }

        long tsMicros = Long.parseLong(parts[0].trim());
        long jobId = Long.parseLong(parts[2].trim());
        int taskIndex = Integer.parseInt(parts[3].trim());
        long machineId = parts[4].isEmpty() ? -1L : Long.parseLong(parts[4].trim());
        int eventType = Integer.parseInt(parts[5].trim());

        return new TaskEvent(tsMicros / 1000L, jobId, taskIndex, machineId, eventType);
    }
}
