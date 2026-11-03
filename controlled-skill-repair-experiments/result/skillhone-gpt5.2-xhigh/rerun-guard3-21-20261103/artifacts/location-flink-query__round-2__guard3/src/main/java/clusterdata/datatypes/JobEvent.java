package clusterdata.datatypes;

import java.io.Serializable;

/**
 * Minimal representation of a Google cluster trace job event.
 *
 * CSV schema (v2.1):
 * timestamp, missing_info, job_id, event_type, user, scheduling_class, job_name, logical_job_name
 */
public class JobEvent implements Serializable {

    public static final int SUBMIT = 0;
    public static final int SCHEDULE = 1;
    public static final int EVICT = 2;
    public static final int FAIL = 3;
    public static final int FINISH = 4;
    public static final int KILL = 5;
    public static final int LOST = 6;

    /** Event timestamp in microseconds since trace start. */
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

    public void setTimestamp(long timestamp) {
        this.timestamp = timestamp;
    }

    public long getJobId() {
        return jobId;
    }

    public void setJobId(long jobId) {
        this.jobId = jobId;
    }

    public int getEventType() {
        return eventType;
    }

    public void setEventType(int eventType) {
        this.eventType = eventType;
    }

    public boolean isTerminal() {
        return eventType == FAIL || eventType == FINISH || eventType == KILL || eventType == LOST;
    }

    public static JobEvent fromCsv(String line) {
        String[] f = line.split(",", -1);
        if (f.length < 4) {
            throw new IllegalArgumentException("Invalid job event line: " + line);
        }

        long ts = Long.parseLong(f[0].trim());
        long jobId = Long.parseLong(f[2].trim());
        int type = Integer.parseInt(f[3].trim());
        return new JobEvent(ts, jobId, type);
    }
}
