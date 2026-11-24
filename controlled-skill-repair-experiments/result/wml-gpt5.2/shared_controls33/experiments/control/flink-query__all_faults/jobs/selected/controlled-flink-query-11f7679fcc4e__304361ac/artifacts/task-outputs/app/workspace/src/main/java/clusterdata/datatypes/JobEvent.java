package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    public static final int FINISH = 4;
    public static final int KILL = 5;
    public static final int FAIL = 3;
    public static final int LOST = 6;

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

    public boolean isTerminalEvent() {
        return eventType == FINISH || eventType == KILL || eventType == FAIL || eventType == LOST;
    }

    public static JobEvent fromCsvLine(String line) {
        String[] f = line.split(",", -1);

        String timestamp = getField(f, 0);
        String missingInfo = getField(f, 1);
        String jobId = getField(f, 2);
        String eventType = getField(f, 3);
        String user = getField(f, 4);
        String schedulingClass = getField(f, 5);
        String jobName = getField(f, 6);
        String logicalJobName = getField(f, 7);

        return new JobEvent(
                parseLong(timestamp, 0L),
                missingInfo,
                parseLong(jobId, -1L),
                parseInt(eventType, -1),
                user,
                parseInt(schedulingClass, -1),
                jobName,
                logicalJobName);
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
}
