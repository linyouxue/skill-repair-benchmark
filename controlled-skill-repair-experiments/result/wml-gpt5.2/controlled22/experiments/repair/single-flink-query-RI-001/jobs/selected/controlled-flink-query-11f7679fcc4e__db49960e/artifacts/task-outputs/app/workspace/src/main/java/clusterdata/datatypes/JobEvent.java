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
        if (line == null || line.isEmpty()) {
            return null;
        }
        // job_events schema (v2.1):
        // 0 time (microseconds), 1 missing_info, 2 job_id, 3 event_type, ...
        String[] p = line.split(",", -1);
        if (p.length < 4) {
            return null;
        }
        if (p[0].isEmpty() || p[2].isEmpty() || p[3].isEmpty()) {
            return null;
        }
        long tsMs = Long.parseLong(p[0]) / 1000L;
        long jobId = Long.parseLong(p[2]);
        int eventType = Integer.parseInt(p[3]);
        return new JobEvent(tsMs, jobId, eventType);
    }

    public long getTimestampMs() {
        return timestampMs;
    }

    public long getJobId() {
        return jobId;
    }

    @Override
    public String toString() {
        return "JobEvent{" +
                "timestampMs=" + timestampMs +
                ", jobId=" + jobId +
                ", eventType=" + eventType +
                '}';
    }
}
