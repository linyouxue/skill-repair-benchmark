package clusterdata.datatypes;

public class JobEvent {

    public static final int EVENT_FAIL = 3;
    public static final int EVENT_FINISH = 4;
    public static final int EVENT_KILL = 5;
    public static final int EVENT_LOST = 6;

    public long timestampMs;
    public long jobId;
    public int eventType;

    public JobEvent() {}

    public JobEvent(long timestampMs, long jobId, int eventType) {
        this.timestampMs = timestampMs;
        this.jobId = jobId;
        this.eventType = eventType;
    }

    public boolean isTerminalEvent() {
        return eventType == EVENT_FAIL || eventType == EVENT_FINISH || eventType == EVENT_KILL || eventType == EVENT_LOST;
    }

    public static JobEvent fromCsvLine(String line) {
        if (line == null) {
            return null;
        }

        String[] parts = line.split(",", -1);
        if (parts.length < 4) {
            return null;
        }

        long tsMicros = Long.parseLong(parts[0].trim());
        long jobId = Long.parseLong(parts[2].trim());
        int eventType = Integer.parseInt(parts[3].trim());

        return new JobEvent(tsMicros / 1000L, jobId, eventType);
    }
}
