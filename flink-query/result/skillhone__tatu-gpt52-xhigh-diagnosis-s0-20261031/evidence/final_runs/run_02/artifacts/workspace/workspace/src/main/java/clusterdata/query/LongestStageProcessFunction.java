package clusterdata.query;

import clusterdata.datatypes.JobEvent;
import clusterdata.datatypes.TaskEvent;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.functions.co.KeyedCoProcessFunction;
import org.apache.flink.util.Collector;

public class LongestStageProcessFunction extends KeyedCoProcessFunction<Long, TaskEvent, JobEvent, Tuple2<Long, Long>> {

    private final long sessionGapMillis;

    private transient ValueState<Long> currentStageCount;
    private transient ValueState<Long> currentStageStart;
    private transient ValueState<Long> lastSubmitTs;
    private transient ValueState<Long> maxStageCount;

    private transient ValueState<Boolean> jobTerminalSeen;
    private transient ValueState<Long> lastJobEventTs;

    private transient ValueState<Long> inactivityTimerTs;
    private transient ValueState<Long> finalizeTimerTs;

    public LongestStageProcessFunction(long sessionGapMillis) {
        this.sessionGapMillis = sessionGapMillis;
    }

    @Override
    public void open(Configuration parameters) {
        currentStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("currentStageCount", Long.class));
        currentStageStart = getRuntimeContext().getState(new ValueStateDescriptor<>("currentStageStart", Long.class));
        lastSubmitTs = getRuntimeContext().getState(new ValueStateDescriptor<>("lastSubmitTs", Long.class));
        maxStageCount = getRuntimeContext().getState(new ValueStateDescriptor<>("maxStageCount", Long.class));

        jobTerminalSeen = getRuntimeContext().getState(new ValueStateDescriptor<>("jobTerminalSeen", Boolean.class));
        lastJobEventTs = getRuntimeContext().getState(new ValueStateDescriptor<>("lastJobEventTs", Long.class));

        inactivityTimerTs = getRuntimeContext().getState(new ValueStateDescriptor<>("inactivityTimerTs", Long.class));
        finalizeTimerTs = getRuntimeContext().getState(new ValueStateDescriptor<>("finalizeTimerTs", Long.class));
    }

    @Override
    public void processElement1(TaskEvent event, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
        if (event.eventType != TaskEvent.EVENT_SUBMIT) {
            return;
        }

        Long lastTs = lastSubmitTs.value();
        long ts = event.timestampMillis();

        if (lastTs == null || ts - lastTs >= sessionGapMillis) {
            closeCurrentStage();
            currentStageStart.update(ts);
            currentStageCount.update(0L);
        }

        Long cnt = currentStageCount.value();
        currentStageCount.update(cnt == null ? 1L : cnt + 1L);
        lastSubmitTs.update(ts);

        registerInactivityTimer(ts, ctx);

        maybeRegisterFinalizeTimer(ctx);
    }

    @Override
    public void processElement2(JobEvent event, Context ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
        if (!event.isTerminal()) {
            return;
        }
        jobTerminalSeen.update(true);
        long ts = event.timestampMillis();
        lastJobEventTs.update(ts);
        maybeRegisterFinalizeTimer(ctx);
    }

    @Override
    public void onTimer(long timestamp, OnTimerContext ctx, Collector<Tuple2<Long, Long>> out) throws Exception {
        Long inactTs = inactivityTimerTs.value();
        if (inactTs != null && timestamp == inactTs) {
            closeCurrentStage();
            inactivityTimerTs.clear();
            maybeRegisterFinalizeTimer(ctx);
        }

        Long finTs = finalizeTimerTs.value();
        if (finTs != null && timestamp == finTs) {
            closeCurrentStage();

            Long maxCnt = maxStageCount.value();
            if (maxCnt == null) {
                maxCnt = 0L;
            }
            out.collect(Tuple2.of(ctx.getCurrentKey(), maxCnt));
            clearAllState();
        }
    }

    private void closeCurrentStage() throws Exception {
        Long cnt = currentStageCount.value();
        if (cnt == null || cnt == 0L) {
            currentStageCount.clear();
            currentStageStart.clear();
            lastSubmitTs.clear();
            return;
        }

        Long maxCnt = maxStageCount.value();
        if (maxCnt == null || cnt > maxCnt) {
            maxStageCount.update(cnt);
        }

        currentStageCount.clear();
        currentStageStart.clear();
        lastSubmitTs.clear();
    }

    private void registerInactivityTimer(long lastSubmitMillis, Context ctx) throws Exception {
        long triggerTs = lastSubmitMillis + sessionGapMillis;

        Long prevTimer = inactivityTimerTs.value();
        if (prevTimer != null) {
            ctx.timerService().deleteEventTimeTimer(prevTimer);
        }
        ctx.timerService().registerEventTimeTimer(triggerTs);
        inactivityTimerTs.update(triggerTs);
    }

    private void maybeRegisterFinalizeTimer(Context ctx) throws Exception {
        Boolean terminal = jobTerminalSeen.value();
        if (terminal == null || !terminal) {
            return;
        }

        Long lastJobTs = lastJobEventTs.value();
        if (lastJobTs == null) {
            return;
        }

        Long lastSubmit = lastSubmitTs.value();
        long maxObserved = lastJobTs;
        if (lastSubmit != null && lastSubmit > maxObserved) {
            maxObserved = lastSubmit;
        }

        long trigger = maxObserved + sessionGapMillis;

        Long prev = finalizeTimerTs.value();
        if (prev == null || trigger > prev) {
            if (prev != null) {
                ctx.timerService().deleteEventTimeTimer(prev);
            }
            ctx.timerService().registerEventTimeTimer(trigger);
            finalizeTimerTs.update(trigger);
        }
    }

    private void clearAllState() throws Exception {
        currentStageCount.clear();
        currentStageStart.clear();
        lastSubmitTs.clear();
        maxStageCount.clear();
        jobTerminalSeen.clear();
        lastJobEventTs.clear();
        inactivityTimerTs.clear();
        finalizeTimerTs.clear();
    }
}
