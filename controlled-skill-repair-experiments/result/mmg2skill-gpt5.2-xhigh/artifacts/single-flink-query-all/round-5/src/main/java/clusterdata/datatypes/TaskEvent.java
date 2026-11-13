package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {

    public static final int SUBMIT = 0;
    public static final int SCHEDULE = 1;
    public static final int EVICT = 2;
    public static final int FAIL = 3;
    public static final int FINISH = 4;
    public static final int KILL = 5;
    public static final int LOST = 6;

    public long timestamp;
    public String missingInfo;
    public long jobId;
    public long taskIndex;
    public long machineId;
    public int eventType;
    public String user;
    public int schedulingClass;
    public int priority;
    public double cpuRequest;
    public double memoryRequest;
    public double diskSpaceRequest;
    public int differentMachinesConstraint;

    public TaskEvent() {
    }

    public TaskEvent(
            long timestamp,
            String missingInfo,
            long jobId,
            long taskIndex,
            long machineId,
            int eventType,
            String user,
            int schedulingClass,
            int priority,
            double cpuRequest,
            double memoryRequest,
            double diskSpaceRequest,
            int differentMachinesConstraint) {
        this.timestamp = timestamp;
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
        this.differentMachinesConstraint = differentMachinesConstraint;
    }

    public static TaskEvent fromCsv(String line) {
        // timestamp,missing info,job ID,task index,machine ID,event type,user name,
        // scheduling class,priority,cpu request,memory request,disk space request,different machines constraint
        String[] parts = line.split(",", -1);
        if (parts.length < 13) {
            throw new IllegalArgumentException("Invalid task event row (expected 13 fields): " + line);
        }

        return new TaskEvent(
                parseLong(parts[0], 0L),
                emptyToNull(parts[1]),
                parseLong(parts[2], 0L),
                parseLong(parts[3], 0L),
                parseLong(parts[4], -1L),
                parseInt(parts[5], -1),
                emptyToNull(parts[6]),
                parseInt(parts[7], -1),
                parseInt(parts[8], -1),
                parseDouble(parts[9], 0.0d),
                parseDouble(parts[10], 0.0d),
                parseDouble(parts[11], 0.0d),
                parseInt(parts[12], 0));
    }

    private static String emptyToNull(String s) {
        return (s == null || s.isEmpty()) ? null : s;
    }

    private static long parseLong(String s, long defaultValue) {
        if (s == null || s.isEmpty()) {
            return defaultValue;
        }
        return Long.parseLong(s);
    }

    private static int parseInt(String s, int defaultValue) {
        if (s == null || s.isEmpty()) {
            return defaultValue;
        }
        return Integer.parseInt(s);
    }

    private static double parseDouble(String s, double defaultValue) {
        if (s == null || s.isEmpty()) {
            return defaultValue;
        }
        return Double.parseDouble(s);
    }
}
