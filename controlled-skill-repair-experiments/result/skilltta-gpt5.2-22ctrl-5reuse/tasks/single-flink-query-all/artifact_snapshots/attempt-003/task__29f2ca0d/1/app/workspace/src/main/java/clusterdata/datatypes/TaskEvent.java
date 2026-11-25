package clusterdata.datatypes;

import java.io.Serializable;
import java.util.Objects;

/**
 * POJO for a row from the Google cluster "task_events" table.
 *
 * <p>Schema (v2.1):
 * <ol>
 *   <li>timestamp (microseconds)</li>
 *   <li>missing info</li>
 *   <li>job ID</li>
 *   <li>task index (within job)</li>
 *   <li>machine ID</li>
 *   <li>event type</li>
 *   <li>user name</li>
 *   <li>scheduling class</li>
 *   <li>priority</li>
 *   <li>resource request for CPU cores</li>
 *   <li>resource request for RAM</li>
 *   <li>resource request for local disk space</li>
 *   <li>different-machine constraint</li>
 * </ol>
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

    private long timestampMicros;
    private String missingInfo;
    private long jobId;
    private long taskIndex;
    private Long machineId;
    private int eventType;
    private String userName;
    private int schedulingClass;
    private int priority;
    private double resourceRequestCpu;
    private double resourceRequestRam;
    private double resourceRequestDisk;
    private int differentMachineConstraint;

    // Needed for Flink POJO.
    public TaskEvent() {}

    public TaskEvent(
            long timestampMicros,
            String missingInfo,
            long jobId,
            long taskIndex,
            Long machineId,
            int eventType,
            String userName,
            int schedulingClass,
            int priority,
            double resourceRequestCpu,
            double resourceRequestRam,
            double resourceRequestDisk,
            int differentMachineConstraint) {
        this.timestampMicros = timestampMicros;
        this.missingInfo = missingInfo;
        this.jobId = jobId;
        this.taskIndex = taskIndex;
        this.machineId = machineId;
        this.eventType = eventType;
        this.userName = userName;
        this.schedulingClass = schedulingClass;
        this.priority = priority;
        this.resourceRequestCpu = resourceRequestCpu;
        this.resourceRequestRam = resourceRequestRam;
        this.resourceRequestDisk = resourceRequestDisk;
        this.differentMachineConstraint = differentMachineConstraint;
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

    public long getTaskIndex() {
        return taskIndex;
    }

    public void setTaskIndex(long taskIndex) {
        this.taskIndex = taskIndex;
    }

    public Long getMachineId() {
        return machineId;
    }

    public void setMachineId(Long machineId) {
        this.machineId = machineId;
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

    public int getPriority() {
        return priority;
    }

    public void setPriority(int priority) {
        this.priority = priority;
    }

    public double getResourceRequestCpu() {
        return resourceRequestCpu;
    }

    public void setResourceRequestCpu(double resourceRequestCpu) {
        this.resourceRequestCpu = resourceRequestCpu;
    }

    public double getResourceRequestRam() {
        return resourceRequestRam;
    }

    public void setResourceRequestRam(double resourceRequestRam) {
        this.resourceRequestRam = resourceRequestRam;
    }

    public double getResourceRequestDisk() {
        return resourceRequestDisk;
    }

    public void setResourceRequestDisk(double resourceRequestDisk) {
        this.resourceRequestDisk = resourceRequestDisk;
    }

    public int getDifferentMachineConstraint() {
        return differentMachineConstraint;
    }

    public void setDifferentMachineConstraint(int differentMachineConstraint) {
        this.differentMachineConstraint = differentMachineConstraint;
    }

    public boolean isSubmitEvent() {
        return eventType == SUBMIT;
    }

    public static TaskEvent fromCsv(String line) {
        String[] parts = line.split(",", -1);
        if (parts.length < 6) {
            return null;
        }

        long timestamp = Long.parseLong(parts[0]);
        String missing = emptyToNull(parts[1]);
        long jobId = Long.parseLong(parts[2]);
        long taskIndex = Long.parseLong(parts[3]);
        Long machineId = parts[4].isEmpty() ? null : Long.parseLong(parts[4]);
        int eventType = Integer.parseInt(parts[5]);

        String userName = parts.length > 6 ? emptyToNull(parts[6]) : null;
        int schedClass = parts.length > 7 && !parts[7].isEmpty() ? Integer.parseInt(parts[7]) : 0;
        int priority = parts.length > 8 && !parts[8].isEmpty() ? Integer.parseInt(parts[8]) : 0;
        double cpu = parts.length > 9 && !parts[9].isEmpty() ? Double.parseDouble(parts[9]) : Double.NaN;
        double ram = parts.length > 10 && !parts[10].isEmpty() ? Double.parseDouble(parts[10]) : Double.NaN;
        double disk = parts.length > 11 && !parts[11].isEmpty() ? Double.parseDouble(parts[11]) : Double.NaN;
        int diff = parts.length > 12 && !parts[12].isEmpty() ? Integer.parseInt(parts[12]) : 0;

        return new TaskEvent(
                timestamp,
                missing,
                jobId,
                taskIndex,
                machineId,
                eventType,
                userName,
                schedClass,
                priority,
                cpu,
                ram,
                disk,
                diff);
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
        if (!(o instanceof TaskEvent)) {
            return false;
        }
        TaskEvent taskEvent = (TaskEvent) o;
        return timestampMicros == taskEvent.timestampMicros
                && jobId == taskEvent.jobId
                && taskIndex == taskEvent.taskIndex
                && eventType == taskEvent.eventType
                && schedulingClass == taskEvent.schedulingClass
                && priority == taskEvent.priority
                && Double.compare(resourceRequestCpu, taskEvent.resourceRequestCpu) == 0
                && Double.compare(resourceRequestRam, taskEvent.resourceRequestRam) == 0
                && Double.compare(resourceRequestDisk, taskEvent.resourceRequestDisk) == 0
                && differentMachineConstraint == taskEvent.differentMachineConstraint
                && Objects.equals(missingInfo, taskEvent.missingInfo)
                && Objects.equals(machineId, taskEvent.machineId)
                && Objects.equals(userName, taskEvent.userName);
    }

    @Override
    public int hashCode() {
        return Objects.hash(
                timestampMicros,
                missingInfo,
                jobId,
                taskIndex,
                machineId,
                eventType,
                userName,
                schedulingClass,
                priority,
                resourceRequestCpu,
                resourceRequestRam,
                resourceRequestDisk,
                differentMachineConstraint);
    }

    @Override
    public String toString() {
        return "TaskEvent{"
                + "timestampMicros="
                + timestampMicros
                + ", jobId="
                + jobId
                + ", taskIndex="
                + taskIndex
                + ", eventType="
                + eventType
                + "}";
    }
}
