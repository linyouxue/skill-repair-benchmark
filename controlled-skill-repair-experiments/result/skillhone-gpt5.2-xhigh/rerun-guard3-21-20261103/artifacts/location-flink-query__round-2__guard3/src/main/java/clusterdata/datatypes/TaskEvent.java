package clusterdata.datatypes;

import java.io.Serializable;

/**
 * Minimal representation of a Google cluster trace task event.
 *
 * CSV schema (v2.1):
 * timestamp, missing_info, job_id, task_index, machine_id, event_type, user, scheduling_class,
 * priority, cpu_request, memory_request, disk_space_request, different_machines_constraint
 */
public class TaskEvent implements Serializable {

    public static final int SUBMIT = 0;
    public static final int SCHEDULE = 1;
    public static final int EVICT = 2;
    public static final int FAIL = 3;
    public static final int FINISH = 4;
    public static final int KILL = 5;
    public static final int LOST = 6;
    public static final int UPDATE_PENDING = 7;
    public static final int UPDATE_RUNNING = 8;

    /** Event timestamp in microseconds since trace start. */
    public long timestamp;

    public long jobId;

    public long taskIndex;

    public int eventType;

    public TaskEvent() {}

    public TaskEvent(long timestamp, long jobId, long taskIndex, int eventType) {
        this.timestamp = timestamp;
        this.jobId = jobId;
        this.taskIndex = taskIndex;
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

    public long getTaskIndex() {
        return taskIndex;
    }

    public void setTaskIndex(long taskIndex) {
        this.taskIndex = taskIndex;
    }

    public int getEventType() {
        return eventType;
    }

    public void setEventType(int eventType) {
        this.eventType = eventType;
    }

    public static TaskEvent fromCsv(String line) {
        String[] f = line.split(",", -1);
        if (f.length < 6) {
            throw new IllegalArgumentException("Invalid task event line: " + line);
        }

        long ts = Long.parseLong(f[0].trim());
        long jobId = Long.parseLong(f[2].trim());

        long taskIndex;
        String taskIndexStr = f[3].trim();
        if (taskIndexStr.isEmpty()) {
            taskIndex = -1L;
        } else {
            taskIndex = Long.parseLong(taskIndexStr);
        }

        int type = Integer.parseInt(f[5].trim());
        return new TaskEvent(ts, jobId, taskIndex, type);
    }
}
