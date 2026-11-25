package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    public static final int EVENT_FINISH = 4;

    public long timestampMicros;
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
            long timestampMicros,
            String missingInfo,
            long jobId,
            int eventType,
            String user,
            int schedulingClass,
            String jobName,
            String logicalJobName) {
        this.timestampMicros = timestampMicros;
        this.missingInfo = missingInfo;
        this.jobId = jobId;
        this.eventType = eventType;
        this.user = user;
        this.schedulingClass = schedulingClass;
        this.jobName = jobName;
        this.logicalJobName = logicalJobName;
    }

    public long timestampMillis() {
        return timestampMicros / 1000L;
    }

    public static JobEvent fromCsvLine(String line) {
        // time, missing info, job ID, event type, user, scheduling class, job name, logical job name
        String[] parts = line.split(",", -1);
        if (parts.length < 8) {
            throw new IllegalArgumentException("Invalid job event line (expected 8 columns): " + line);
        }

        long timestampMicros = parseLong(parts[0], 0L);
        String missingInfo = emptyToNull(parts[1]);
        long jobId = parseLong(parts[2], -1L);
        int eventType = (int) parseLong(parts[3], -1L);
        String user = emptyToNull(parts[4]);
        int schedulingClass = (int) parseLong(parts[5], -1L);
        String jobName = emptyToNull(parts[6]);
        String logicalJobName = emptyToNull(parts[7]);

        return new JobEvent(
                timestampMicros,
                missingInfo,
                jobId,
                eventType,
                user,
                schedulingClass,
                jobName,
                logicalJobName);
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
}
