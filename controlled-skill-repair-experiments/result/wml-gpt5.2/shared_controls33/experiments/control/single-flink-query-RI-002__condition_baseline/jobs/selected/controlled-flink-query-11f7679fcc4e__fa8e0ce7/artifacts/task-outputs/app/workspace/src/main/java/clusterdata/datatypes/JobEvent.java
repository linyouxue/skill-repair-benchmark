package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    public static final int SUBMIT = 0;
    public static final int SCHEDULE = 1;
    public static final int EVICT = 2;
    public static final int FAIL = 3;
    public static final int FINISH = 4;
    public static final int KILL = 5;
    public static final int LOST = 6;

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

    public boolean isTerminal() {
        return eventType == FAIL || eventType == FINISH || eventType == KILL || eventType == LOST;
    }

    public static JobEvent fromCsvLine(String line) {
        // job events table fields (v2.1):
        // 1 timestamp, 2 missing info, 3 job ID, 4 event type, ...
        String[] parts = line.split(",", -1);
        if (parts.length < 4) {
            throw new IllegalArgumentException("Invalid job event line: " + line);
        }

        long ts = Long.parseLong(parts[0]);
        long jobId = Long.parseLong(parts[2]);
        int eventType = Integer.parseInt(parts[3]);
        return new JobEvent(ts, jobId, eventType);
    }
}
