# Adaptive Cruise Control (ACC) Report

## System design

### Architecture
The simulation is split into three layers:

1. **PID controllers** (`pid_controller.py`)
   - Generic discrete PID implementation with conditional integration (anti-windup).
2. **ACC decision + control** (`acc_system.py`)
   - Converts sensed ego/lead states into a longitudinal acceleration command.
3. **Scenario + vehicle integration** (`simulation.py`)
   - Uses `sensor_data.csv` to provide lead-vehicle presence and lead speed.
   - Uses the measured `distance` only to **initialize** the lead position when the lead first appears (and when it re-appears after being absent). After that, the gap evolves from kinematics.

### Modes
The ACC selects one of three modes each timestep:

- **cruise**: no lead vehicle detected (`lead_speed` or `distance` is missing in the sensor data)
  - Speed PID tracks `set_speed` (30 m/s).

- **follow**: lead present and not in an emergency condition
  - Speed PID still tries to reach/hold `set_speed`.
  - A **brake-only distance PID** is applied when the ego vehicle is closer than the desired safe gap, overriding the speed command with stronger braking.

- **emergency**: lead present and either
  - time-to-collision (TTC) is below the configured threshold (3.0 s), or
  - the gap is below the configured minimum gap (10 m)

In emergency, the controller commands the maximum allowed deceleration.

### Safety features
- **Acceleration limits** are always enforced: `[-8.0, 3.0] m/s²`.
- **Hard minimum-gap enforcement**: if `distance < min_distance`, the system immediately switches to `emergency`.
- **TTC emergency braking**: if `TTC < emergency_ttc_threshold`, the system switches to `emergency`.

### Distance error definition (reported)
In `simulation_results.csv`, the `distance_error` field is reported as a *distance deficit*:

- `distance_error = max(0, desired_gap - actual_distance)`
- where `desired_gap = ego_speed * time_headway + min_distance`

So:
- `distance_error = 0` means the ego vehicle is at or beyond the desired safe gap.
- Positive values mean the ego vehicle is closer than the desired safe gap by that many meters.

This is the safety-relevant error for an ACC controller.

## PID tuning methodology and final gains

### Method
- Start with conservative speed gains to avoid overshoot.
- Tune the distance controller as a brake-only controller to reduce gap deficits without trying to “pull” the vehicle closer when it is already safe.
- Use a small grid/manual search while checking:
  - speed rise time, overshoot, and steady-state error in the initial cruise phase
  - minimum achieved distance (collision avoidance)
  - steady-state distance deficit during following

### Final tuned gains (`tuning_results.yaml`)
```yaml
pid_speed:
  kp: 0.4
  ki: 0.05
  kd: 0.0
pid_distance:
  kp: 0.8
  ki: 0.0
  kd: 1.0
```

## Simulation results and performance metrics

### Run configuration
- Duration: **150 s** (1501 samples)
- Timestep: **0.1 s**
- Set speed: **30 m/s**
- Time headway: **1.5 s**
- Minimum gap: **10 m**
- Emergency TTC threshold: **3.0 s**

### Key results (from `simulation_results.csv`)

| Metric | Target | Result |
|---|---:|---:|
| Speed rise time (10%→90%) | < 10 s | ~ 8.5 s |
| Speed overshoot | < 5% | ~ 3.78% |
| Speed steady-state error (cruise) | < 0.5 m/s | ~ 0.24 m/s |
| Distance steady-state error (distance deficit, follow) | < 2 m | ~ 0.04 m |
| Minimum distance | > 5 m | ~ 19.38 m |

### Mode usage summary
- `cruise`: 501 samples
- `follow`: 983 samples
- `emergency`: 17 samples

Emergency events are triggered by TTC or the hard minimum-gap safety rule and command maximum braking.
