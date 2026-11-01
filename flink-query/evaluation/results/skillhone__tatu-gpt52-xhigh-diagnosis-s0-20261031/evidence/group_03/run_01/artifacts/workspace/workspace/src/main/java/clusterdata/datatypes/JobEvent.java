package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    public static final int EVENT_SUBMIT = 0;
    public static final int EVENT_SCHEDULE = 1;
    public static final int EVENT_FINISH = 4;
    public static final int EVENT_KILL = 5;

    public long timestampUs;
    public long jobId;
    public int eventType;

    public JobEvent() {}

    public JobEvent(long timestampUs, long jobId, int eventType) {
        this.timestampUs = timestampUs;
        this.jobId = jobId;
        this.eventType = eventType;
    }

    public long timestampMs() {
        return timestampUs / 1000L;
    }

    /**
     * Parses the v2.1 job_events CSV format.
     *
     * Columns (relevant):
     * 0 timestamp (microseconds), 2 job_id, 3 event_type.
     */
    public static JobEvent fromCsvLine(String line) {
        if (line == null || line.isEmpty()) {
            return null;
        }

        String[] parts = line.split(",", -1);
        if (parts.length < 4) {
            return null;
        }

        long timestampUs = Long.parseLong(parts[0]);
        long jobId = Long.parseLong(parts[2]);
        int eventType = parts[3].isEmpty() ? -1 : Integer.parseInt(parts[3]);

        return new JobEvent(timestampUs, jobId, eventType);
    }
}
