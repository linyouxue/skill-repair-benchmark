package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    public static final int EVENT_FAIL = 3;
    public static final int EVENT_FINISH = 4;
    public static final int EVENT_KILL = 5;
    public static final int EVENT_LOST = 6;

    public long timestampMs;
    public long jobId;
    public int eventType;

    public JobEvent() {}

    public JobEvent(long timestampMs, long jobId, int eventType) {
        this.timestampMs = timestampMs;
        this.jobId = jobId;
        this.eventType = eventType;
    }

    public boolean isTerminal() {
        return eventType == EVENT_FAIL || eventType == EVENT_FINISH || eventType == EVENT_KILL || eventType == EVENT_LOST;
    }

    public static JobEvent fromCsvLine(String line) {
        String[] parts = line.split(",", -1);
        long timestampUs = Long.parseLong(parts[0]);
        long jobId = Long.parseLong(parts[2]);
        int eventType = Integer.parseInt(parts[3]);
        return new JobEvent(timestampUs / 1000L, jobId, eventType);
    }
}
