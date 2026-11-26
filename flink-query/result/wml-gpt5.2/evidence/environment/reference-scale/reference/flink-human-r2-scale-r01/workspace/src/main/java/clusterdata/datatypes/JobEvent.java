package clusterdata.datatypes;

import java.io.Serializable;

public class JobEvent implements Serializable {

    public static final int FINISH = 4;

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

    public boolean isFinish() {
        return eventType == FINISH;
    }

    /**
     * Expected schema (job_events):
     * time,missing info,job ID,event type,...
     */
    public static JobEvent fromCsvLine(String line) {
        if (line == null || line.isEmpty()) {
            return null;
        }

        String[] parts = line.split(",", -1);
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
}
