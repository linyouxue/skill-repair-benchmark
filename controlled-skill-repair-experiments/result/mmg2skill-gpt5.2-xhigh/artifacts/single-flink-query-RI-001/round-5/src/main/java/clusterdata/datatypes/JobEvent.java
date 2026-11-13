package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    public static final int EVENT_TYPE_SUBMIT = 0;
    public static final int EVENT_TYPE_SCHEDULE = 1;
    public static final int EVENT_TYPE_EVICT = 2;
    public static final int EVENT_TYPE_FAIL = 3;
    public static final int EVENT_TYPE_FINISH = 4;
    public static final int EVENT_TYPE_KILL = 5;
    public static final int EVENT_TYPE_LOST = 6;

    public long timestampMicros;
    public long jobId;
    public int eventType;

    public JobEvent() {}

    public JobEvent(long timestampMicros, long jobId, int eventType) {
        this.timestampMicros = timestampMicros;
        this.jobId = jobId;
        this.eventType = eventType;
    }

    public long getTimestampMicros() {
        return timestampMicros;
    }

    public long getTimestampMillis() {
        return timestampMicros / 1000L;
    }

    public long getJobId() {
        return jobId;
    }

    public int getEventType() {
        return eventType;
    }

    public boolean isTerminal() {
        return eventType == EVENT_TYPE_FAIL
                || eventType == EVENT_TYPE_FINISH
                || eventType == EVENT_TYPE_KILL
                || eventType == EVENT_TYPE_LOST;
    }

    public static JobEvent fromCsvLine(String line) {
        String[] parts = line.split(",", -1);
        if (parts.length < 4) {
            throw new IllegalArgumentException("Invalid job event line: " + line);
        }

        long timestampMicros = Long.parseLong(parts[0]);
        long jobId = Long.parseLong(parts[2]);
        int eventType = Integer.parseInt(parts[3]);
        return new JobEvent(timestampMicros, jobId, eventType);
    }
}
