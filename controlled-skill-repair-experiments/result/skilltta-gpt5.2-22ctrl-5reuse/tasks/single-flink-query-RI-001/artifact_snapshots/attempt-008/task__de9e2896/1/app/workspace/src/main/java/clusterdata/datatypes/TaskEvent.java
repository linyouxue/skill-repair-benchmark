package clusterdata.datatypes;

import java.io.Serializable;

public class TaskEvent implements Serializable {
    public static final int EVENT_SUBMIT = 0;

    public long timestampMicros;
    public String missingInfo;
    public long jobId;
    public long taskIndex;
    public long machineId;
    public int eventType;

    public TaskEvent() {}

    public TaskEvent(
            long timestampMicros,
            String missingInfo,
            long jobId,
            long taskIndex,
            long machineId,
            int eventType) {
        this.timestampMicros = timestampMicros;
        this.missingInfo = missingInfo;
        this.jobId = jobId;
        this.taskIndex = taskIndex;
        this.machineId = machineId;
        this.eventType = eventType;
    }

    public long getTimestampMillis() {
        return timestampMicros / 1_000L;
    }

    public long getJobId() {
        return jobId;
    }
}
