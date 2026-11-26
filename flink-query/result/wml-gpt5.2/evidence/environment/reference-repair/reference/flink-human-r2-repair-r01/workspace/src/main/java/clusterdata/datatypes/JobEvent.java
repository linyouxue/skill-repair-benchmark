package clusterdata.datatypes;

import java.io.Serializable;

/**
 * Minimal JobEvent representation for Google cluster traces job_events table.
 */
public class JobEvent implements Serializable {

    public static final int EVENT_SUBMIT = 0;
    public static final int EVENT_SCHEDULE = 1;
    public static final int EVENT_FAIL = 3;
    public static final int EVENT_FINISH = 4;
    public static final int EVENT_KILL = 5;

    public long timestamp;
    public long jobId;
    public int eventType;

    // Flink POJO requires a public no-arg constructor.
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

    public boolean isFinish() {
        return eventType == EVENT_FINISH;
    }

    public static JobEvent fromCsvLine(String line) {
        if (line == null || line.isEmpty()) {
            return null;
        }
        String[] parts = line.split(",", -1);
        if (parts.length < 4) {
            return null;
        }
        long timestamp = parseLong(parts[0]);
        long jobId = parseLong(parts[2]);
        int eventType = parseInt(parts[3]);
        return new JobEvent(timestamp, jobId, eventType);
    }

    private static long parseLong(String s) {
        if (s == null || s.isEmpty()) {
            return 0L;
        }
        return Long.parseLong(s);
    }

    private static int parseInt(String s) {
        if (s == null || s.isEmpty()) {
            return 0;
        }
        return Integer.parseInt(s);
    }
}
