package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    public static final int EVENT_FAIL = 3;
    public static final int EVENT_FINISH = 4;
    public static final int EVENT_KILL = 5;
    public static final int EVENT_LOST = 6;

    public long timestampUs;
    public long jobId;
    public int eventType;

    public JobEvent() {}

    public JobEvent(long timestampUs, long jobId, int eventType) {
        this.timestampUs = timestampUs;
        this.jobId = jobId;
        this.eventType = eventType;
    }

    public long getTimestampMillis() {
        return timestampUs / 1000L;
    }

    public boolean isTerminal() {
        return eventType == EVENT_FAIL
                || eventType == EVENT_FINISH
                || eventType == EVENT_KILL
                || eventType == EVENT_LOST;
    }

    public static JobEvent fromCsvLine(String line) {
        if (line == null || line.isEmpty() || line.charAt(0) == '#') {
            return null;
        }

        String[] fields = line.split(",", -1);
        if (fields.length < 4) {
            return null;
        }

        try {
            long timestampUs = parseLong(fields[0], -1L);
            long jobId = parseLong(fields[2], -1L);
            int eventType = parseInt(fields[3], -1);

            if (timestampUs < 0 || jobId < 0 || eventType < 0) {
                return null;
            }

            return new JobEvent(timestampUs, jobId, eventType);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static long parseLong(String value, long defaultValue) {
        if (value == null || value.isEmpty()) {
            return defaultValue;
        }
        return Long.parseLong(value);
    }

    private static int parseInt(String value, int defaultValue) {
        if (value == null || value.isEmpty()) {
            return defaultValue;
        }
        return Integer.parseInt(value);
    }
}
