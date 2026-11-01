package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {

    public static final int EVENT_SUBMIT = 0;

    public long timestampUs;
    public long jobId;
    public long taskIndex;
    public int eventType;

    public TaskEvent() {}

    public TaskEvent(long timestampUs, long jobId, long taskIndex, int eventType) {
        this.timestampUs = timestampUs;
        this.jobId = jobId;
        this.taskIndex = taskIndex;
        this.eventType = eventType;
    }

    public long timestampMs() {
        return timestampUs / 1000L;
    }

    /**
     * Parses the v2.1 task_events CSV format.
     *
     * Columns (relevant):
     * 0 timestamp (microseconds), 2 job_id, 3 task_index, 5 event_type.
     */
    public static TaskEvent fromCsvLine(String line) {
        if (line == null || line.isEmpty()) {
            return null;
        }

        String[] parts = line.split(",", -1);
        if (parts.length < 6) {
            return null;
        }

        long timestampUs = Long.parseLong(parts[0]);
        long jobId = Long.parseLong(parts[2]);
        long taskIndex = parts[3].isEmpty() ? -1L : Long.parseLong(parts[3]);
        int eventType = parts[5].isEmpty() ? -1 : Integer.parseInt(parts[5]);

        return new TaskEvent(timestampUs, jobId, taskIndex, eventType);
    }
}
