package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    // Event time in milliseconds.
    public long timestamp;
    public long jobId;
    public int eventType;

    public JobEvent() {
    }

    public JobEvent(long timestamp, long jobId, int eventType) {
        this.timestamp = timestamp;
        this.jobId = jobId;
        this.eventType = eventType;
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

    public boolean isTerminal() {
        // v2.1 schema uses the same codes as task events:
        // 3=FAIL, 4=FINISH, 5=KILL.
        return eventType == 3 || eventType == 4 || eventType == 5;
    }

    public static JobEvent fromCsvLine(String line) {
        // job_events schema (v2.1):
        // time, missing info, job ID, event type, user, scheduling class,
        // job name, logical job name
        String[] f = line.split(",", -1);
        long tsMicros = parseLong(f, 0);
        long jobId = parseLong(f, 2);
        int eventType = parseInt(f, 3);
        long tsMillis = tsMicros / 1000L;
        return new JobEvent(tsMillis, jobId, eventType);
    }

    private static long parseLong(String[] f, int idx) {
        if (idx >= f.length) {
            return 0L;
        }
        String s = f[idx];
        if (s == null || s.isEmpty()) {
            return 0L;
        }
        return Long.parseLong(s);
    }

    private static int parseInt(String[] f, int idx) {
        if (idx >= f.length) {
            return 0;
        }
        String s = f[idx];
        if (s == null || s.isEmpty()) {
            return 0;
        }
        return Integer.parseInt(s);
    }
}
