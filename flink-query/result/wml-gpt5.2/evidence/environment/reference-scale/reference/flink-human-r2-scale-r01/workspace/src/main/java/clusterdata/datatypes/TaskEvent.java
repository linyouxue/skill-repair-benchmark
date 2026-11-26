package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {

    public static final int SUBMIT = 0;

    public long timestamp;
    public long jobId;
    public long taskIndex;
    public int eventType;

    public TaskEvent() {
    }

    public TaskEvent(long timestamp, long jobId, long taskIndex, int eventType) {
        this.timestamp = timestamp;
        this.jobId = jobId;
        this.taskIndex = taskIndex;
        this.eventType = eventType;
    }

    public boolean isSubmit() {
        return eventType == SUBMIT;
    }

    /**
     * Expected schema (task_events):
     * time,missing info,job ID,task index,machine ID,event type,...
     */
    public static TaskEvent fromCsvLine(String line) {
        if (line == null || line.isEmpty()) {
            return null;
        }

        String[] parts = line.split(",", -1);
        if (parts.length < 6) {
            return null;
        }

        try {
            long ts = Long.parseLong(parts[0]);
            long jobId = Long.parseLong(parts[2]);
            long taskIndex = parts[3].isEmpty() ? -1L : Long.parseLong(parts[3]);
            int eventType = Integer.parseInt(parts[5]);
            return new TaskEvent(ts, jobId, taskIndex, eventType);
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
