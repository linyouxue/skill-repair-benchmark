package clusterdata.datatypes;

public class JobEvent {
    public long timestamp;
    public long jobId;
    public int eventType;

    public JobEvent() {}

    public JobEvent(long timestamp, long jobId, int eventType) {
        this.timestamp = timestamp;
        this.jobId = jobId;
        this.eventType = eventType;
    }

    public long getTimestampMs() {
        return timestamp / 1000L;
    }
}
