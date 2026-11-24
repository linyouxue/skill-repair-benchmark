package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {

    public static final int EVENT_SUBMIT = 0;

    public long timestamp;
    public String missingInfo;
    public long jobId;
    public long taskIndex;
    public Long machineId;
    public int eventType;
    public String user;
    public Integer schedulingClass;
    public Integer priority;
    public Double cpuRequest;
    public Double memoryRequest;
    public Double diskSpaceRequest;
    public Integer differentMachinesConstraint;

    public TaskEvent() {
    }

    public static TaskEvent fromCsv(String line) {
        String[] parts = line.split(",", -1);
        if (parts.length < 6) {
            throw new IllegalArgumentException("Invalid task event row (too few columns): " + line);
        }

        TaskEvent e = new TaskEvent();
        e.timestamp = parseLongRequired(parts[0]);
        e.missingInfo = emptyToNull(parts[1]);
        e.jobId = parseLongRequired(parts[2]);
        e.taskIndex = parseLongRequired(parts[3]);
        e.machineId = parseLongNullable(parts[4]);
        e.eventType = parseIntRequired(parts[5]);
        e.user = parts.length > 6 ? emptyToNull(parts[6]) : null;
        e.schedulingClass = parts.length > 7 ? parseIntNullable(parts[7]) : null;
        e.priority = parts.length > 8 ? parseIntNullable(parts[8]) : null;
        e.cpuRequest = parts.length > 9 ? parseDoubleNullable(parts[9]) : null;
        e.memoryRequest = parts.length > 10 ? parseDoubleNullable(parts[10]) : null;
        e.diskSpaceRequest = parts.length > 11 ? parseDoubleNullable(parts[11]) : null;
        e.differentMachinesConstraint = parts.length > 12 ? parseIntNullable(parts[12]) : null;
        return e;
    }

    private static String emptyToNull(String s) {
        return (s == null || s.isEmpty()) ? null : s;
    }

    private static long parseLongRequired(String s) {
        if (s == null || s.isEmpty()) {
            throw new IllegalArgumentException("Missing required long field");
        }
        return Long.parseLong(s);
    }

    private static Long parseLongNullable(String s) {
        return (s == null || s.isEmpty()) ? null : Long.parseLong(s);
    }

    private static int parseIntRequired(String s) {
        if (s == null || s.isEmpty()) {
            throw new IllegalArgumentException("Missing required int field");
        }
        return Integer.parseInt(s);
    }

    private static Integer parseIntNullable(String s) {
        return (s == null || s.isEmpty()) ? null : Integer.parseInt(s);
    }

    private static Double parseDoubleNullable(String s) {
        return (s == null || s.isEmpty()) ? null : Double.parseDouble(s);
    }
}
