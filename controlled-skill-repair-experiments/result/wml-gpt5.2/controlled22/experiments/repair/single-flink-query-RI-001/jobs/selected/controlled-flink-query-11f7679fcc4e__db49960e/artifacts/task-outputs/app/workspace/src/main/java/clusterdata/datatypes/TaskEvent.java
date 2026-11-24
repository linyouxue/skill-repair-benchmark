package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {

    public static final int EVENT_SUBMIT = 0;

    public long timestampMs;
    public long jobId;
    public long taskIndex;
    public int eventType;

    public TaskEvent() {}

    public TaskEvent(long timestampMs, long jobId, long taskIndex, int eventType) {
        this.timestampMs = timestampMs;
        this.jobId = jobId;
        this.taskIndex = taskIndex;
        this.eventType = eventType;
    }

    public boolean isSubmit() {
        return eventType == EVENT_SUBMIT;
    }

    public static TaskEvent fromCsvLine(String line) {
        if (line == null || line.isEmpty()) {
            return null;
        }
        // task_events schema (v2.1):
        // 0 time (microseconds), 1 missing_info, 2 job_id, 3 task_index, 4 machine_id,
        // 5 event_type, ...
        String[] p = line.split(",", -1);
        if (p.length < 6) {
            return null;
        }
        if (p[0].isEmpty() || p[2].isEmpty() || p[3].isEmpty() || p[5].isEmpty()) {
            return null;
        }
        long tsMs = Long.parseLong(p[0]) / 1000L;
        long jobId = Long.parseLong(p[2]);
        long taskIndex = Long.parseLong(p[3]);
        int eventType = Integer.parseInt(p[5]);
        return new TaskEvent(tsMs, jobId, taskIndex, eventType);
    }

    public long getTimestampMs() {
        return timestampMs;
    }

    public long getJobId() {
        return jobId;
    }

    @Override
    public String toString() {
        return "TaskEvent{" +
                "timestampMs=" + timestampMs +
                ", jobId=" + jobId +
                ", taskIndex=" + taskIndex +
                ", eventType=" + eventType +
                '}';
    }
}
