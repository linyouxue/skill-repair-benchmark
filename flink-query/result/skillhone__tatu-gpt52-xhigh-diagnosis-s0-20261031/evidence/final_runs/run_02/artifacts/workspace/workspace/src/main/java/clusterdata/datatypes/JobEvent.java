package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    public static final int EVENT_SUBMIT = 0;
    public static final int EVENT_SCHEDULE = 1;
    public static final int EVENT_FAIL = 3;
    public static final int EVENT_FINISH = 4;
    public static final int EVENT_KILL = 5;

    public long timestamp; // microseconds
    public long jobId;
    public int eventType;

    public JobEvent() {}

    public JobEvent(long timestamp, long jobId, int eventType) {
        this.timestamp = timestamp;
        this.jobId = jobId;
        this.eventType = eventType;
    }

    public long timestampMillis() {
        return timestamp / 1000L;
    }

    public boolean isTerminal() {
        return eventType == EVENT_FAIL || eventType == EVENT_FINISH || eventType == EVENT_KILL;
    }

    public static JobEvent fromCsvLine(String line) {
        String[] parts = line.split(",", -1);
        // Schema (v2.1):
        // 0 time, 1 missing info, 2 job id, 3 event type, ...
        long ts = parseLong(parts, 0, 0L);
        long jobId = parseLong(parts, 2, -1L);
        int eventType = (int) parseLong(parts, 3, -1L);
        return new JobEvent(ts, jobId, eventType);
    }

    private static long parseLong(String[] parts, int idx, long defaultVal) {
        if (idx >= parts.length) {
            return defaultVal;
        }
        String s = parts[idx];
        if (s == null || s.isEmpty()) {
            return defaultVal;
        }
        return Long.parseLong(s);
    }
}
