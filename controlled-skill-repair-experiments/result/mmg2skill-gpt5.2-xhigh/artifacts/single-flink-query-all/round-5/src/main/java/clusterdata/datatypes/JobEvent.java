package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

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
    public int eventType;
    public String user;
    public int schedulingClass;
    public String jobName;
    public String logicalJobName;

    public JobEvent() {
    }

    public JobEvent(
            long timestamp,
            String missingInfo,
            long jobId,
            int eventType,
            String user,
            int schedulingClass,
            String jobName,
            String logicalJobName) {
        this.timestamp = timestamp;
        this.missingInfo = missingInfo;
        this.jobId = jobId;
        this.eventType = eventType;
        this.user = user;
        this.schedulingClass = schedulingClass;
        this.jobName = jobName;
        this.logicalJobName = logicalJobName;
    }

    public static JobEvent fromCsv(String line) {
        // timestamp,missing info,job ID,event type,user name,scheduling class,job name,logical job name
        String[] parts = line.split(",", -1);
        if (parts.length < 8) {
            throw new IllegalArgumentException("Invalid job event row (expected 8 fields): " + line);
        }

        return new JobEvent(
                parseLong(parts[0], 0L),
                emptyToNull(parts[1]),
                parseLong(parts[2], 0L),
                parseInt(parts[3], -1),
                emptyToNull(parts[4]),
                parseInt(parts[5], -1),
                emptyToNull(parts[6]),
                emptyToNull(parts[7]));
    }

    public boolean isTerminalEvent() {
        return eventType == FAIL || eventType == FINISH || eventType == KILL || eventType == LOST;
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
}
