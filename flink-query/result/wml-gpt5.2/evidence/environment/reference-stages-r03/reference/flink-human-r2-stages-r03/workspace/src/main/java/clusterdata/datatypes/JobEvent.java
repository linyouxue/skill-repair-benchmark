package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    public static final int EVENT_SUBMIT = 0;
    public static final int EVENT_SCHEDULE = 1;
    public static final int EVENT_FINISH = 4;

    public long timestamp;
    public long jobId;
    public int eventType;

    public JobEvent() {}

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

    public static JobEvent fromCsvLine(String line) {
        String[] parts = line.split(",", -1);
        if (parts.length < 4) {
            throw new IllegalArgumentException("Invalid job event line: " + line);
        }
        long timestamp = Long.parseLong(parts[0]);
        long jobId = Long.parseLong(parts[2]);
        int eventType = Integer.parseInt(parts[3]);
        return new JobEvent(timestamp, jobId, eventType);
    }
}
