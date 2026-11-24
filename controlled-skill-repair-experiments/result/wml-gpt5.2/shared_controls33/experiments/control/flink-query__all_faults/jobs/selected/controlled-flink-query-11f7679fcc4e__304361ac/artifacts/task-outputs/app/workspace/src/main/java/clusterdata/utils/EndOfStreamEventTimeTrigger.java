package clusterdata.utils;

import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.streaming.api.windowing.triggers.Trigger;
import org.apache.flink.streaming.api.windowing.triggers.TriggerResult;
import org.apache.flink.streaming.api.windowing.windows.GlobalWindow;
import org.apache.flink.streaming.api.windowing.windows.Window;

public class EndOfStreamEventTimeTrigger<T, W extends Window> extends Trigger<T, W> {

    private static final long serialVersionUID = 1L;

    private final long triggerTime;

    private final ValueStateDescriptor<Boolean> timerRegisteredDesc =
            new ValueStateDescriptor<>("end_of_stream_timer_registered", Boolean.class);

    public EndOfStreamEventTimeTrigger(long triggerTime) {
        this.triggerTime = triggerTime;
    }

    public static <T> EndOfStreamEventTimeTrigger<T, GlobalWindow> forGlobalWindow() {
        return new EndOfStreamEventTimeTrigger<>(Long.MAX_VALUE - 1);
    }

    @Override
    public TriggerResult onElement(T element, long timestamp, W window, TriggerContext ctx) throws Exception {
        ValueState<Boolean> timerRegistered = ctx.getPartitionedState(timerRegisteredDesc);
        Boolean already = timerRegistered.value();
        if (already == null || !already) {
            ctx.registerEventTimeTimer(triggerTime);
            timerRegistered.update(true);
        }
        return TriggerResult.CONTINUE;
    }

    @Override
    public TriggerResult onProcessingTime(long time, W window, TriggerContext ctx) {
        return TriggerResult.CONTINUE;
    }

    @Override
    public TriggerResult onEventTime(long time, W window, TriggerContext ctx) throws Exception {
        if (time == triggerTime) {
            return TriggerResult.FIRE_AND_PURGE;
        }
        return TriggerResult.CONTINUE;
    }

    @Override
    public void clear(W window, TriggerContext ctx) throws Exception {
        ctx.deleteEventTimeTimer(triggerTime);
        ValueState<Boolean> timerRegistered = ctx.getPartitionedState(timerRegisteredDesc);
        timerRegistered.clear();
    }
}
