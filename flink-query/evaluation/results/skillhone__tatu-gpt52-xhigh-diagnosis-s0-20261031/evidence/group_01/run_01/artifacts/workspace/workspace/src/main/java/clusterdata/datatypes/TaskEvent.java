package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {

    public static final int EVENT_SUBMIT = 0;

    public long timestampUs;
    public long jobId;
    public long taskIndex;
    public int eventType;

    public TaskEvent() {}

    public TaskEvent(long timestampUs, long jobId, long taskIndex, int eventType) {
        this.timestampUs = timestampUs;
        this.jobId = jobId;
        this.taskIndex = taskIndex;
        this.eventType = eventType;
    }

    public long getTimestampMillis() {
        return timestampUs / 1000L;
    }

    public static TaskEvent fromCsvLine(String line) {
        if (line == null || line.isEmpty() || line.charAt(0) == '#') {
            return null;
        }

        String[] fields = line.split(",", -1);
        if (fields.length < 6) {
            return null;
        }

        try {
            long timestampUs = parseLong(fields[0], -1L);
            long jobId = parseLong(fields[2], -1L);
            long taskIndex = parseLong(fields[3], -1L);
            int eventType = parseInt(fields[5], -1);

            if (timestampUs < 0 || jobId < 0 || eventType < 0) {
                return null;
            }

            return new TaskEvent(timestampUs, jobId, taskIndex, eventType);
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
