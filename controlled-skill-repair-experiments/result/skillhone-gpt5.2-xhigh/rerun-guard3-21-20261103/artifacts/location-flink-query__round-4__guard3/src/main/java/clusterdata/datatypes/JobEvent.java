package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    public static final int EVENT_FAIL = 3;
    public static final int EVENT_FINISH = 4;
    public static final int EVENT_KILL = 5;

    private final long timestampMicros;
    private final long jobId;
    private final int eventType;

    public JobEvent(long timestampMicros, long jobId, int eventType) {
        this.timestampMicros = timestampMicros;
        this.jobId = jobId;
        this.eventType = eventType;
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
        return eventType == EVENT_FAIL || eventType == EVENT_FINISH || eventType == EVENT_KILL;
    }

    public static JobEvent fromCsvLine(String line) {
        if (line == null || line.isEmpty()) {
            return null;
        }

        String[] parts = line.split(",", -1);
        if (parts.length < 4) {
            throw new IllegalArgumentException("Invalid job event line: " + line);
        }

        long timestampMicros = parseLong(parts[0], 0L);
        long jobId = parseLong(parts[2], -1L);
        int eventType = (int) parseLong(parts[3], -1L);

        return new JobEvent(timestampMicros, jobId, eventType);
    }

    private static long parseLong(String value, long defaultValue) {
        if (value == null || value.isEmpty()) {
            return defaultValue;
        }
        return Long.parseLong(value);
    }
}
