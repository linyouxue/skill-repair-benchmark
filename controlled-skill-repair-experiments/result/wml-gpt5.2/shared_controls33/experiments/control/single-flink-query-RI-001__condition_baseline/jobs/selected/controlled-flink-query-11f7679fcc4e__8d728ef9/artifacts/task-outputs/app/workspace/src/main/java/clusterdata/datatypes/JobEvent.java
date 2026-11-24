package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    public static final int EVENT_FAIL = 3;
    public static final int EVENT_FINISH = 4;
    public static final int EVENT_KILL = 5;

    public static boolean isTerminal(int eventType) {
        return eventType == EVENT_FAIL || eventType == EVENT_FINISH || eventType == EVENT_KILL;
    }

    public long timestamp;
    public String missingInfo;
    public long jobId;
    public int eventType;
    public String user;
    public Integer schedulingClass;
    public String jobName;
    public String logicalJobName;

    public JobEvent() {
    }

    public static JobEvent fromCsv(String line) {
        String[] parts = line.split(",", -1);
        if (parts.length < 4) {
            throw new IllegalArgumentException("Invalid job event row (too few columns): " + line);
        }

        JobEvent e = new JobEvent();
        e.timestamp = parseLongRequired(parts[0]);
        e.missingInfo = emptyToNull(parts[1]);
        e.jobId = parseLongRequired(parts[2]);
        e.eventType = parseIntRequired(parts[3]);
        e.user = parts.length > 4 ? emptyToNull(parts[4]) : null;
        e.schedulingClass = parts.length > 5 ? parseIntNullable(parts[5]) : null;
        e.jobName = parts.length > 6 ? emptyToNull(parts[6]) : null;
        e.logicalJobName = parts.length > 7 ? emptyToNull(parts[7]) : null;
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

    private static int parseIntRequired(String s) {
        if (s == null || s.isEmpty()) {
            throw new IllegalArgumentException("Missing required int field");
        }
        return Integer.parseInt(s);
    }

    private static Integer parseIntNullable(String s) {
        return (s == null || s.isEmpty()) ? null : Integer.parseInt(s);
    }
}
