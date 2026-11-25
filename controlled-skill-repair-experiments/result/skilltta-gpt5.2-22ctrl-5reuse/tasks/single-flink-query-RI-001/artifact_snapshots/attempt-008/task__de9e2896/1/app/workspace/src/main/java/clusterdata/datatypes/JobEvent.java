package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {
    public static final int EVENT_SUBMIT = 0;
    public static final int EVENT_SCHEDULE = 1;
    public static final int EVENT_EVICT = 2;
    public static final int EVENT_FAIL = 3;
    public static final int EVENT_FINISH = 4;
    public static final int EVENT_KILL = 5;
    public static final int EVENT_LOST = 6;

    public long timestampMicros;
    public String missingInfo;
    public long jobId;
    public int eventType;

    public JobEvent() {}

    public JobEvent(long timestampMicros, String missingInfo, long jobId, int eventType) {
        this.timestampMicros = timestampMicros;
        this.missingInfo = missingInfo;
        this.jobId = jobId;
        this.eventType = eventType;
    }

    public long getTimestampMillis() {
        return timestampMicros / 1_000L;
    }

    public long getJobId() {
        return jobId;
    }

    public boolean isTerminal() {
        return eventType == EVENT_FINISH || eventType == EVENT_KILL || eventType == EVENT_LOST;
    }
}
