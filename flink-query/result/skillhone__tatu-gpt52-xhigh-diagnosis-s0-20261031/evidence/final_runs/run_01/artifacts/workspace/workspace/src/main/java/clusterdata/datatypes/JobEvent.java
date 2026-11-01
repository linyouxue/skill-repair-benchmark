package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    public static final int EVENT_SUBMIT = 0;
    public static final int EVENT_SCHEDULE = 1;
    public static final int EVENT_FAIL = 3;
    public static final int EVENT_FINISH = 4;
    public static final int EVENT_KILL = 5;

    public long timestampUs;
    public long timestampMs;
    public long jobId;
    public int eventType;

    public JobEvent() {
    }

    public JobEvent(long timestampUs, long jobId, int eventType) {
        this.timestampUs = timestampUs;
        this.timestampMs = timestampUs / 1000L;
        this.jobId = jobId;
        this.eventType = eventType;
    }

    public static JobEvent fromCsvLine(String line) {
        if (line == null) {
            return null;
        }
        String[] parts = line.split(",", -1);
        if (parts.length < 4) {
            return null;
        }

        long timestampUs;
        long jobId;
        int eventType;
        try {
            timestampUs = Long.parseLong(parts[0]);
            jobId = Long.parseLong(parts[2]);
            eventType = Integer.parseInt(parts[3]);
        } catch (NumberFormatException e) {
            return null;
        }

        return new JobEvent(timestampUs, jobId, eventType);
    }

    public boolean isTerminalEvent() {
        return eventType == EVENT_FAIL || eventType == EVENT_FINISH || eventType == EVENT_KILL;
    }
}
