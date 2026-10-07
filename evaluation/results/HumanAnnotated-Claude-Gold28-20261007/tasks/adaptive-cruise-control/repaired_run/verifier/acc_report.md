# Adaptive Cruise Control (ACC) Simulation Report

## 1. System Design

### 1.1 Architecture

The ACC system is composed of three decoupled modules:

| File | Responsibility |
|---|---|
| `pid_controller.py` | Generic discrete-time PID controller (`PIDController` class). |
| `acc_system.py` | High-level ACC logic (`AdaptiveCruiseControl` class): mode selection, PID orchestration, actuator-limit enforcement. |
| `simulation.py` | 150 s closed-loop simulator: reads tuned gains from `tuning_results.yaml`, feeds lead-vehicle data from `sensor_data.csv`, integrates kinematics. |

The ACC controller receives `(ego_speed, lead_speed, distance, dt)` every 100 ms and returns `(acceleration_cmd, mode, distance_error)`. The simulator then clamps the command to the vehicle's physical limits (`[-8.0, +3.0] m/s²`) and integrates the kinematic model.

### 1.2 Operating Modes

Mode selection runs on every tick, before computing acceleration:

| Mode | Condition | Control law |
|---|---|---|
| **cruise** | `lead_speed is None` (no vehicle ahead). | Speed PID: `error = set_speed − ego_speed`. |
| **emergency** | A lead is present **and** `TTC < 3.0 s`. | Open-loop maximum braking: `a = −8.0 m/s²`. |
| **follow** | Lead present, `TTC ≥ 3.0 s` (or `TTC` undefined, i.e. not approaching). | Distance PID on `error = distance − safe_distance`, where `safe_distance = headway·v_ego + d_min`. |

Transitioning between modes **resets the integrator of the inactive PID** so stale accumulation cannot kick in when control is handed back.

### 1.3 Safety Features

1. **Time-headway spacing policy** — target gap grows linearly with speed:
   `safe_distance = 1.5 s · v_ego + 10.0 m`.
2. **TTC-based emergency braking** — when the predicted collision time drops below 3.0 s, the controller commands full brake regardless of PID state.
3. **Actuator saturation** — acceleration clamped to `[-8.0, +3.0] m/s²` at both the ACC output and the simulator input (defense in depth).
4. **Speed floor** — `ego_speed` is never allowed to go negative (vehicle cannot roll backwards).
5. **Mode-change integrator reset** — prevents windup carrying from cruise into follow (and vice-versa).

### 1.4 Scenario (sensor_data.csv)

- **t = 0 – 30 s** — no lead vehicle → *cruise* from 0 to 30 m/s.
- **t = 30 – 130 s** — lead vehicle appears (initial gap 52.1 m, lead speed oscillating 0 – 36.8 m/s, including a hard stop around t ≈ 124 s) → *follow* with brief *emergency* interventions.
- **t = 130 – 150 s** — lead disappears → *cruise* back to 30 m/s.

## 2. PID Tuning Methodology

### 2.1 Approach

Tuning was performed offline (`tune.py`) via a two-stage grid search against the actual 150 s scenario. `simulation.py` does **no** auto-tuning — it loads the final gains from `tuning_results.yaml` at startup.

**Stage 1 — Speed PID** (cruise mode only, t = 0 – 30 s):
Grid over `kp ∈ {0.3, 0.5, 0.8, 1.0, 1.5, 2.0}`, `ki ∈ {0, 0.05, 0.1, 0.2, 0.5}`, `kd ∈ {0, 0.05, 0.1}`.
Scoring: feasibility against `rise < 10 s`, `overshoot < 5 %`, `SSE < 0.5 m/s`, then minimize rise time → overshoot → SSE.

**Stage 2 — Distance PID** (follow mode), with the speed gains fixed from Stage 1:
Grid over `kp ∈ {0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0}`, `ki ∈ {0, 0.01, 0.05, 0.1, 0.2}`, `kd ∈ {1.0, 2.0, 3.0, 4.0, 4.5}`.
Scoring: feasibility against `|SSE| < 2 m` and `min_distance > 5 m`, then minimize steady-segment SSE.

### 2.2 Metric Definitions

Because the lead vehicle's speed is non-stationary (σ ≈ 5.5 m/s overall), a global "steady-state error" is meaningless. Following the `simulation-metrics` skill ("evaluate mean absolute error in each steady segment"), we identify the window **t = 40 – 70 s** where the lead speed is approximately constant (σ < 1 m/s, mean ≈ 25 m/s) and compute

```
distance_SSE = mean( |distance − safe_distance| )   over 40 s ≤ t ≤ 70 s
```

The same window and metric are used both for tuning and for the final validation reported below. The `min_distance` statistic uses the entire follow interval so emergency transients are not hidden.

### 2.3 Final Gains

```yaml
pid_speed:
  kp: 2.0
  ki: 0.0
  kd: 0.0
pid_distance:
  kp: 0.8
  ki: 0.2
  kd: 1.0
```

**Rationale:**
- Speed loop: with `kp = 2.0` the initial error of 30 m/s immediately saturates the throttle (`2.0 × 30 = 60 ≫ 3`), giving maximum legal acceleration until near the setpoint. Because the plant is a pure integrator with no bias (no drag or gravity in the kinematic model), `ki = kd = 0` is sufficient — the setpoint is reached with zero steady-state error and no overshoot.
- Distance loop: `kd = 1.0` provides heavy damping — the derivative of `(distance − safe_distance)` is approximately `(v_lead − v_ego) − h·a_ego`, so `kd` effectively adds a relative-velocity feedforward that avoids oscillation. `kp = 0.8` sets the restoring stiffness, and a small `ki = 0.2` eliminates bias during long constant-speed following.

All six gains satisfy the required ranges `kp ∈ (0, 10)`, `ki ∈ [0, 5)`, `kd ∈ [0, 5)`.

## 3. Simulation Results

The 1501-sample closed-loop run is in `simulation_results.csv` (columns `time, ego_speed, acceleration_cmd, mode, distance_error, distance, ttc`).

### 3.1 Performance Metrics vs. Targets

| Metric | Target | Measured | Pass |
|---|---|---|---|
| Speed rise time (10 % → 90 % of 30 m/s) | < 10 s | **8.00 s** | ✓ |
| Speed overshoot | < 5 % | **0.00 %** | ✓ |
| Speed settling time (2 % band) | — | 10.00 s | — |
| Speed SSE (final 5 s of initial cruise) | < 0.5 m/s | **0.000 m/s** | ✓ |
| Distance SSE (steady window 40 – 70 s) | < 2 m | **0.254 m** | ✓ |
| Minimum inter-vehicle distance | > 5 m | **18.27 m** | ✓ |
| Final cruise SSE (130 – 150 s) | — | 0.059 m/s | ✓ |
| Control duration | 150 s | 150.0 s (1501 samples) | ✓ |

### 3.2 Mode Usage

| Mode | Samples | Duration |
|---|---|---|
| cruise | 501 | 50.1 s |
| follow | 983 | 98.3 s |
| emergency | 17 | 1.7 s |

Emergency braking fired briefly around the lead vehicle's hard stop near t ≈ 124 s — exactly the situation the TTC guard is designed for. The controller recovered to `follow` within ~1.7 s with no collision (min distance 18.27 m).

### 3.3 Qualitative Behavior

- **0 – 10 s**: full-throttle acceleration (saturated at +3.0 m/s²) from rest.
- **10 – 30 s**: speed holds at 30 m/s with no overshoot (speed loop at zero error).
- **30 – 40 s**: lead appears 52 m ahead at 25 m/s; ego decelerates smoothly to match ~25 m/s, closing the gap toward the time-headway target.
- **40 – 70 s**: tight tracking of the lead (SSE 0.25 m).
- **70 – 120 s**: lead speed varies between 20 – 37 m/s; ego mirrors it with small lag, saturating the actuator only during the sharpest transients.
- **~ 124 s**: lead stops abruptly → TTC < 3 s → emergency mode → max braking → recover.
- **130 – 150 s**: lead gone, cruise control returns ego to 30 m/s.

### 3.4 Reproducibility

```bash
python3 tune.py        # regenerates tuning_results.yaml (offline, optional)
python3 simulation.py  # reads vehicle_params.yaml + tuning_results.yaml,
                       # produces simulation_results.csv
python3 analyze.py     # prints the metrics in §3.1
```

`simulation.py` is deterministic and self-contained; it never imports from `tune.py`.
