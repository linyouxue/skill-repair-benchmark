package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    public static final int SUBMIT = 0;
    public static final int SCHEDULE = 1;
    public static final int FAIL = 3;
    public static final int FINISH = 4;
    public static final int KILL = 5;

    public long timestamp;
    public long jobId;
    public int eventType;

    public JobEvent() {}

    public JobEvent(long timestamp, long jobId, int eventType) {
        this.timestamp = timestamp;
        this.jobId = jobId;
        this.eventType = eventType;
    }

    public static JobEvent fromCsv(String line) {
        if (line == null) {
            return null;
        }
        String trimmed = line.trim();
        if (trimmed.isEmpty()) {
            return null;
        }

        String[] parts = trimmed.split(",", -1);
        if (parts.length < 4) {
            return null;
        }

        try {
            long ts = Long.parseLong(parts[0]);
            long jobId = Long.parseLong(parts[2]);
            int eventType = Integer.parseInt(parts[3]);
            return new JobEvent(ts, jobId, eventType);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    public boolean isFinish() {
        return eventType == FINISH;
    }

    public long getTimestamp() {
        return timestamp;
    }

    public long getTime() {
        return timestamp;
    }

    public long getJobId() {
        return jobId;
    }

    public int getEventType() {
        return eventType;
    }

    public void setTimestamp(long timestamp) {
        this.timestamp = timestamp;
    }

    public void setTime(long timestamp) {
        this.timestamp = timestamp;
    }

    public void setJobId(long jobId) {
        this.jobId = jobId;
    }

    public void setEventType(int eventType) {
        this.eventType = eventType;
    }
}
