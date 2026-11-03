package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

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

    public static boolean isTerminalEventType(int eventType) {
        return eventType == 3 || eventType == 4 || eventType == 5 || eventType == 6;
    }
}
