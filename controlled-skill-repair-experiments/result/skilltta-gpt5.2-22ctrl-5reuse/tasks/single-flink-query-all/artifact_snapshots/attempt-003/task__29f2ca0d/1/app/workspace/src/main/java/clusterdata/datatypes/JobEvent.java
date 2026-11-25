package clusterdata.datatypes;

import java.io.Serializable;
import java.util.Objects;

/**
 * POJO for a row from the Google cluster "job_events" table.
 *
 * <p>Schema (v2.1):
 * <ol>
 *   <li>timestamp (microseconds)</li>
 *   <li>missing info</li>
 *   <li>job ID</li>
 *   <li>event type</li>
 *   <li>user name</li>
 *   <li>scheduling class</li>
 *   <li>job name</li>
 *   <li>logical job name</li>
 * </ol>
 */
public class JobEvent implements Serializable {

    public static final int SUBMIT = 0;
    public static final int SCHEDULE = 1;
    public static final int EVICT = 2;
    public static final int FAIL = 3;
    public static final int FINISH = 4;
    public static final int KILL = 5;
    public static final int LOST = 6;
    public static final int UPDATE_PENDING = 7;
    public static final int UPDATE_RUNNING = 8;

    private long timestampMicros;
    private String missingInfo;
    private long jobId;
    private int eventType;
    private String userName;
    private int schedulingClass;
    private String jobName;
    private String logicalJobName;

    // Needed for Flink POJO.
    public JobEvent() {}

    public JobEvent(
            long timestampMicros,
            String missingInfo,
            long jobId,
            int eventType,
            String userName,
            int schedulingClass,
            String jobName,
            String logicalJobName) {
        this.timestampMicros = timestampMicros;
        this.missingInfo = missingInfo;
        this.jobId = jobId;
        this.eventType = eventType;
        this.userName = userName;
        this.schedulingClass = schedulingClass;
        this.jobName = jobName;
        this.logicalJobName = logicalJobName;
    }

    public long getTimestampMicros() {
        return timestampMicros;
    }

    public void setTimestampMicros(long timestampMicros) {
        this.timestampMicros = timestampMicros;
    }

    public long getTimestampMillis() {
        return timestampMicros / 1000L;
    }

    public String getMissingInfo() {
        return missingInfo;
    }

    public void setMissingInfo(String missingInfo) {
        this.missingInfo = missingInfo;
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

    public String getUserName() {
        return userName;
    }

    public void setUserName(String userName) {
        this.userName = userName;
    }

    public int getSchedulingClass() {
        return schedulingClass;
    }

    public void setSchedulingClass(int schedulingClass) {
        this.schedulingClass = schedulingClass;
    }

    public String getJobName() {
        return jobName;
    }

    public void setJobName(String jobName) {
        this.jobName = jobName;
    }

    public String getLogicalJobName() {
        return logicalJobName;
    }

    public void setLogicalJobName(String logicalJobName) {
        this.logicalJobName = logicalJobName;
    }

    /**
     * "Job finished" for this query means the job reached a terminal state.
     */
    public boolean isTerminalEvent() {
        return eventType == FINISH || eventType == FAIL || eventType == KILL || eventType == LOST;
    }

    public static JobEvent fromCsv(String line) {
        // Keep empty columns (missing info) with -1.
        String[] parts = line.split(",", -1);
        if (parts.length < 4) {
            return null;
        }

        long timestamp = Long.parseLong(parts[0]);
        String missing = emptyToNull(parts[1]);
        long jobId = Long.parseLong(parts[2]);
        int eventType = Integer.parseInt(parts[3]);
        String user = parts.length > 4 ? emptyToNull(parts[4]) : null;
        int schedClass = parts.length > 5 && !parts[5].isEmpty() ? Integer.parseInt(parts[5]) : 0;
        String jobName = parts.length > 6 ? emptyToNull(parts[6]) : null;
        String logicalJobName = parts.length > 7 ? emptyToNull(parts[7]) : null;

        return new JobEvent(timestamp, missing, jobId, eventType, user, schedClass, jobName, logicalJobName);
    }

    private static String emptyToNull(String s) {
        if (s == null) {
            return null;
        }
        String t = s.trim();
        return t.isEmpty() ? null : t;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) {
            return true;
        }
        if (!(o instanceof JobEvent)) {
            return false;
        }
        JobEvent jobEvent = (JobEvent) o;
        return timestampMicros == jobEvent.timestampMicros
                && jobId == jobEvent.jobId
                && eventType == jobEvent.eventType
                && schedulingClass == jobEvent.schedulingClass
                && Objects.equals(missingInfo, jobEvent.missingInfo)
                && Objects.equals(userName, jobEvent.userName)
                && Objects.equals(jobName, jobEvent.jobName)
                && Objects.equals(logicalJobName, jobEvent.logicalJobName);
    }

    @Override
    public int hashCode() {
        return Objects.hash(
                timestampMicros,
                missingInfo,
                jobId,
                eventType,
                userName,
                schedulingClass,
                jobName,
                logicalJobName);
    }

    @Override
    public String toString() {
        return "JobEvent{"
                + "timestampMicros="
                + timestampMicros
                + ", jobId="
                + jobId
                + ", eventType="
                + eventType
                + "}";
    }
}
