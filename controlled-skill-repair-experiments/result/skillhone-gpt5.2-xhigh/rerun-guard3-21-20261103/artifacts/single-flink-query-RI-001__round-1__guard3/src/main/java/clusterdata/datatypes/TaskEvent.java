package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {

    // Event time in milliseconds.
    public long timestamp;
    public long jobId;
    public int taskIndex;
    public int eventType;

    public TaskEvent() {
    }

    public TaskEvent(long timestamp, long jobId, int taskIndex, int eventType) {
        this.timestamp = timestamp;
        this.jobId = jobId;
        this.taskIndex = taskIndex;
        this.eventType = eventType;
    }

    public long getTimestamp() {
        return timestamp;
    }

    public long getJobId() {
        return jobId;
    }

    public int getTaskIndex() {
        return taskIndex;
    }

    public int getEventType() {
        return eventType;
    }

    public boolean isSubmit() {
        return eventType == 0;
    }

    public static TaskEvent fromCsvLine(String line) {
        // task_events schema (v2.1):
        // time, missing info, job ID, task index, machine ID, event type, user,
        // scheduling class, priority, cpu request, memory request, disk space request,
        // different-machine constraint
        String[] f = line.split(",", -1);
        long tsMicros = parseLong(f, 0);
        long jobId = parseLong(f, 2);
        int taskIndex = parseInt(f, 3);
        int eventType = parseInt(f, 5);
        long tsMillis = tsMicros / 1000L;
        return new TaskEvent(tsMillis, jobId, taskIndex, eventType);
    }

    private static long parseLong(String[] f, int idx) {
        if (idx >= f.length) {
            return 0L;
        }
        String s = f[idx];
        if (s == null || s.isEmpty()) {
            return 0L;
        }
        return Long.parseLong(s);
    }

    private static int parseInt(String[] f, int idx) {
        if (idx >= f.length) {
            return 0;
        }
        String s = f[idx];
        if (s == null || s.isEmpty()) {
            return 0;
        }
        return Integer.parseInt(s);
    }
}
