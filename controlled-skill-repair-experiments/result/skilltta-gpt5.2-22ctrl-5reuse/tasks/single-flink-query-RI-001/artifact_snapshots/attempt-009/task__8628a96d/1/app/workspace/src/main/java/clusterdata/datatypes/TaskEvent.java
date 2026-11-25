package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {

    public static final int EVENT_SUBMIT = 0;

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
    public double memoryRequest;
    public double diskSpaceRequest;
    public int differentMachinesRestriction;

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
            double memoryRequest,
            double diskSpaceRequest,
            int differentMachinesRestriction) {
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
        this.memoryRequest = memoryRequest;
        this.diskSpaceRequest = diskSpaceRequest;
        this.differentMachinesRestriction = differentMachinesRestriction;
    }

    public long timestampMillis() {
        return timestampMicros / 1000L;
    }

    public static TaskEvent fromCsvLine(String line) {
        // time, missing info, job ID, task index, machine ID, event type, user,
        // scheduling class, priority, cpu request, memory request, disk space request,
        // different machines restriction
        String[] parts = line.split(",", -1);
        if (parts.length < 13) {
            throw new IllegalArgumentException("Invalid task event line (expected 13 columns): " + line);
        }

        long timestampMicros = parseLong(parts[0], 0L);
        String missingInfo = emptyToNull(parts[1]);
        long jobId = parseLong(parts[2], -1L);
        int taskIndex = (int) parseLong(parts[3], -1L);
        long machineId = parseLong(parts[4], -1L);
        int eventType = (int) parseLong(parts[5], -1L);
        String user = emptyToNull(parts[6]);
        int schedulingClass = (int) parseLong(parts[7], -1L);
        int priority = (int) parseLong(parts[8], -1L);
        double cpuRequest = parseDouble(parts[9], 0.0d);
        double memoryRequest = parseDouble(parts[10], 0.0d);
        double diskSpaceRequest = parseDouble(parts[11], 0.0d);
        int differentMachinesRestriction = (int) parseLong(parts[12], 0L);

        return new TaskEvent(
                timestampMicros,
                missingInfo,
                jobId,
                taskIndex,
                machineId,
                eventType,
                user,
                schedulingClass,
                priority,
                cpuRequest,
                memoryRequest,
                diskSpaceRequest,
                differentMachinesRestriction);
    }

    private static String emptyToNull(String s) {
        if (s == null || s.isEmpty()) {
            return null;
        }
        return s;
    }

    private static long parseLong(String s, long defaultValue) {
        if (s == null || s.isEmpty()) {
            return defaultValue;
        }
        return Long.parseLong(s);
    }

    private static double parseDouble(String s, double defaultValue) {
        if (s == null || s.isEmpty()) {
            return defaultValue;
        }
        return Double.parseDouble(s);
    }
}
