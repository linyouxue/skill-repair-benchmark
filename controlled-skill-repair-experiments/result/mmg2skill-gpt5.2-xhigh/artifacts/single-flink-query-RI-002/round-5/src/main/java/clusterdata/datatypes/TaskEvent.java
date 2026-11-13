package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {
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
    public double diskRequest;
    public int differentMachineConstraint;

    public TaskEvent() {
    }

    public static TaskEvent fromCsvLine(String line) {
        String[] parts = line.split(",", -1);
        if (parts.length < 6) {
            return null;
        }

        TaskEvent e = new TaskEvent();
        e.timestamp = parseLongOrDefault(parts, 0, 0L) / 1000L;
        e.missingInfo = emptyToNull(parts, 1);
        e.jobId = parseLongOrDefault(parts, 2, 0L);
        e.taskIndex = parseLongOrDefault(parts, 3, 0L);
        e.machineId = parseLongOrDefault(parts, 4, -1L);
        e.eventType = parseIntOrDefault(parts, 5, -1);
        e.user = emptyToNull(parts, 6);
        e.schedulingClass = parseIntOrDefault(parts, 7, -1);
        e.priority = parseIntOrDefault(parts, 8, -1);
        e.cpuRequest = parseDoubleOrDefault(parts, 9, Double.NaN);
        e.memoryRequest = parseDoubleOrDefault(parts, 10, Double.NaN);
        e.diskRequest = parseDoubleOrDefault(parts, 11, Double.NaN);
        e.differentMachineConstraint = parseIntOrDefault(parts, 12, 0);
        return e;
    }

    public long getTimestamp() {
        return timestamp;
    }

    public long getJobId() {
        return jobId;
    }

    public int getEventType() {
        return eventType;
    }

    private static long parseLongOrDefault(String[] parts, int idx, long defaultValue) {
        if (idx >= parts.length || parts[idx].isEmpty()) {
            return defaultValue;
        }
        return Long.parseLong(parts[idx]);
    }

    private static int parseIntOrDefault(String[] parts, int idx, int defaultValue) {
        if (idx >= parts.length || parts[idx].isEmpty()) {
            return defaultValue;
        }
        return Integer.parseInt(parts[idx]);
    }

    private static double parseDoubleOrDefault(String[] parts, int idx, double defaultValue) {
        if (idx >= parts.length || parts[idx].isEmpty()) {
            return defaultValue;
        }
        return Double.parseDouble(parts[idx]);
    }

    private static String emptyToNull(String[] parts, int idx) {
        if (idx >= parts.length) {
            return null;
        }
        return parts[idx].isEmpty() ? null : parts[idx];
    }
}
