package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {
    public long timestamp;
    public String missingInfo;
    public long jobId;
    public int eventType;
    public String user;
    public int schedulingClass;
    public String jobName;
    public String logicalJobName;

    public JobEvent() {
    }

    public static JobEvent fromCsvLine(String line) {
        String[] parts = line.split(",", -1);
        if (parts.length < 4) {
            return null;
        }

        JobEvent e = new JobEvent();
        e.timestamp = parseLongOrDefault(parts, 0, 0L) / 1000L;
        e.missingInfo = emptyToNull(parts, 1);
        e.jobId = parseLongOrDefault(parts, 2, 0L);
        e.eventType = parseIntOrDefault(parts, 3, -1);
        e.user = emptyToNull(parts, 4);
        e.schedulingClass = parseIntOrDefault(parts, 5, -1);
        e.jobName = emptyToNull(parts, 6);
        e.logicalJobName = emptyToNull(parts, 7);
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

    private static String emptyToNull(String[] parts, int idx) {
        if (idx >= parts.length) {
            return null;
        }
        return parts[idx].isEmpty() ? null : parts[idx];
    }
}
