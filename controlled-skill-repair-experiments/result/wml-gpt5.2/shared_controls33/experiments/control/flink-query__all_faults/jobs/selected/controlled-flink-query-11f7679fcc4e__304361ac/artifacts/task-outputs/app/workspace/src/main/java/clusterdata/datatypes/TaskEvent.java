package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {

    public static final int SUBMIT = 0;

    public long timestampMicros;
    public String missingInfo;
    public long jobId;
    public int taskIndex;
    public long machineId;
    public int eventType;
    public String user;
    public int schedulingClass;
    public int priority;
    public double cpuRequest;
    public double ramRequest;
    public double diskRequest;
    public int differentMachineConstraint;

    public TaskEvent() {
    }

    public TaskEvent(
            long timestampMicros,
            String missingInfo,
            long jobId,
            int taskIndex,
            long machineId,
            int eventType,
            String user,
            int schedulingClass,
            int priority,
            double cpuRequest,
            double ramRequest,
            double diskRequest,
            int differentMachineConstraint) {
        this.timestampMicros = timestampMicros;
        this.missingInfo = missingInfo;
        this.jobId = jobId;
        this.taskIndex = taskIndex;
        this.machineId = machineId;
        this.eventType = eventType;
        this.user = user;
        this.schedulingClass = schedulingClass;
        this.priority = priority;
        this.cpuRequest = cpuRequest;
        this.ramRequest = ramRequest;
        this.diskRequest = diskRequest;
        this.differentMachineConstraint = differentMachineConstraint;
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

    public int getEventType() {
        return eventType;
    }

    public static TaskEvent fromCsvLine(String line) {
        String[] f = line.split(",", -1);

        String timestamp = getField(f, 0);
        String missingInfo = getField(f, 1);
        String jobId = getField(f, 2);
        String taskIndex = getField(f, 3);
        String machineId = getField(f, 4);
        String eventType = getField(f, 5);
        String user = getField(f, 6);
        String schedulingClass = getField(f, 7);
        String priority = getField(f, 8);
        String cpu = getField(f, 9);
        String ram = getField(f, 10);
        String disk = getField(f, 11);
        String diff = getField(f, 12);

        return new TaskEvent(
                parseLong(timestamp, 0L),
                missingInfo,
                parseLong(jobId, -1L),
                parseInt(taskIndex, -1),
                parseLong(machineId, -1L),
                parseInt(eventType, -1),
                user,
                parseInt(schedulingClass, -1),
                parseInt(priority, -1),
                parseDouble(cpu, 0.0),
                parseDouble(ram, 0.0),
                parseDouble(disk, 0.0),
                parseInt(diff, 0));
    }

    private static String getField(String[] f, int idx) {
        if (idx >= f.length) {
            return "";
        }
        return f[idx].trim();
    }

    private static long parseLong(String s, long def) {
        if (s == null || s.isEmpty()) {
            return def;
        }
        return Long.parseLong(s);
    }

    private static int parseInt(String s, int def) {
        if (s == null || s.isEmpty()) {
            return def;
        }
        return Integer.parseInt(s);
    }

    private static double parseDouble(String s, double def) {
        if (s == null || s.isEmpty()) {
            return def;
        }
        return Double.parseDouble(s);
    }
}
