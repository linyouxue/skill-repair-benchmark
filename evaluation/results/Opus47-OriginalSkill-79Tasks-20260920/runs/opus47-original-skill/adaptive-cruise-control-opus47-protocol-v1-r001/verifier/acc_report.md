# Adaptive Cruise Control — Design & Simulation Report

## 1. System Design

### 1.1 Architecture

The ACC stack has three cooperating modules:

| File | Role |
|------|------|
| `pid_controller.py` | Reusable discrete-time PID with output clamping and back-calculation anti-windup |
| `acc_system.py` | Mode-switching controller (`cruise` / `follow` / `emergency`) that composes two PIDs |
| `simulation.py` | Vehicle kinematic simulator; reads `vehicle_params.yaml` + `tuning_results.yaml` and drives the ACC with `sensor_data.csv` |

Data flow per timestep (`dt = 0.1 s`):

```
sensor_data.csv  ──►  (lead_speed, distance)
                              │
                              ▼
             AdaptiveCruiseControl.compute()
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
     cruise               follow                emergency
   speed PID           distance PID          max_decel = -8 m/s²
        │                     │                     │
        └──────────► acceleration_cmd ◄─────────────┘
                              │
                              ▼
                 ego_speed ← integrate(a, dt)
                 sim_distance ← integrate((v_lead-v_ego), dt)
```

Distance is **simulated**, not read blindly from the CSV: the first sample after the lead vehicle enters the sensor range initialises `sim_distance`, and thereafter it evolves from the relative velocity so that the closed-loop dynamics are self-consistent with the ACC's actions.

### 1.2 Modes and Safety Features

* **`cruise`** — Active when `lead_speed` is `None`. Speed PID drives the ego toward the 30 m/s set point; controller state is reset on entry to avoid stale integrator windup after re-acquisition.
* **`follow`** — Active when a lead vehicle is detected and TTC is safe. The distance PID acts on `distance − (v_ego · t_headway + d_min)` (safe-headway model with `t_headway = 1.5 s`, `d_min = 10 m`). The output is additionally capped by the speed-PID's proportional cruise term so the ego never exceeds the set speed while following.
* **`emergency`** — Triggered when `TTC < 3.0 s`. Overrides both PIDs and commands the physical deceleration limit `-8.0 m/s²`.

Safety features:

1. Actuator saturation `[-8.0, 3.0] m/s²` enforced both in the PID output clamps and again in the vehicle integrator.
2. Back-calculation anti-windup: when the PID output is clamped, the last integrator increment is rolled back.
3. Non-negative speed constraint (`v_ego ≥ 0`).
4. Time-Headway policy that scales safe distance with velocity — a bigger buffer at higher speeds.
5. Emergency TTC override bypasses controller state so a fresh recovery starts as soon as danger clears.

## 2. PID Tuning

### 2.1 Methodology

Gains were selected by an offline grid search (`tune.py`), simulating the whole 150 s scenario for each candidate and rejecting any that violated a target:

* **Speed PID** — evaluated on the 0–30 s cruise phase. Metrics: rise time (10 % → 90 %), overshoot, and steady-state error over the final 20 % window. All three must satisfy `rise < 10 s`, `overshoot < 5 %`, `SSE < 0.5 m/s`. Amongst passing candidates the tie-breaker is `(overshoot, SSE, rise time)`.
* **Distance PID** — evaluated on the 40–70 s quasi-steady window, i.e. where the lead vehicle's speed (~25 m/s) is comfortably below the set point so a true steady state is physically reachable. Requirements: `|SSE| < 2 m` **and** `min sim_distance > 5 m` over the entire follow/emergency portion. The tie-breaker favours smaller SSE, then larger minimum distance.

The grids searched (all within the required ranges `kp ∈ (0, 10)`, `ki ∈ [0, 5)`, `kd ∈ [0, 5)`):

* Speed:   `kp ∈ {0.5, 0.8, 1.0, 1.5, 2.0}`, `ki ∈ {0, 0.05, 0.1, 0.2}`, `kd ∈ {0, 0.1, 0.2, 0.5}`
* Distance: `kp ∈ {0.2, 0.3, 0.5, 0.8, 1.0, 1.5}`, `ki ∈ {0, 0.02, 0.05, 0.1}`, `kd ∈ {0, 0.1, 0.2, 0.5}`

### 2.2 Final Gains (`tuning_results.yaml`)

| Controller | Kp | Ki | Kd |
|-----------|----|----|----|
| **pid_speed**    | 2.0 | 0.0  | 0.0 |
| **pid_distance** | 0.2 | 0.1  | 0.1 |

**Discussion.** The speed loop is dominated by the actuator limit: `Kp · error = 2.0 · 30 = 60 m/s²` is far above `+3 m/s²`, so during acceleration the command is permanently saturated. This means the physical `max_acceleration` — not the PID gains — determines the rise time (a linear 0 → 30 m/s ramp lasts 10 s, giving the 8 s 10 %–90 % rise). No integral term is needed because there is no unmodelled disturbance and the plant is a pure integrator; adding `Ki` only risks post-saturation overshoot. `Kd = 0` because the error signal has no useful derivative here.

The distance loop uses a mild proportional gain to avoid over-braking when the lead vehicle first appears, a small integral term to eliminate the residual offset caused by the time-headway policy tracking a moving reference, and a light derivative term to damp the transient at mode entry. This combination yields sub-decimetre steady-state distance error while keeping the minimum inter-vehicle gap comfortably above the 5 m safety threshold.

## 3. Simulation Results

### 3.1 Scenario

* Duration: **150.0 s**, **1501** samples at `dt = 0.1 s`.
* Cruise phase: `t ∈ [0, 30) s` — no lead vehicle.
* Follow / emergency phase: `t ∈ [30, 130) s` — lead vehicle detected; lead speed varies from ~24 m/s to ~35 m/s including a hard-braking event at `t ≈ 120 s` (lead drops to ~5 m/s).
* Cruise phase again: `t ∈ [130, 150] s` — lead vehicle out of range.

### 3.2 Mode Distribution

| Mode | Samples | Duration |
|------|---------|---------:|
| cruise    | 501 | 50.1 s |
| follow    | 981 | 98.1 s |
| emergency |  19 | 1.9 s |

### 3.3 Performance Metrics vs. Targets

| Metric | Target | Measured | Result |
|--------|-------:|---------:|:------:|
| Speed rise time (10 %–90 %)    | < 10 s   | **8.00 s**  | ✅ PASS |
| Speed overshoot                | < 5 %    | **0.00 %**  | ✅ PASS |
| Speed steady-state error       | < 0.5 m/s| **0.000 m/s** | ✅ PASS |
| Speed 2 % settling time        | —         | 10.0 s      | — |
| Distance steady-state error (40–70 s window) | < 2 m | **0.099 m** | ✅ PASS |
| Minimum inter-vehicle distance | > 5 m    | **9.36 m**  | ✅ PASS |
| Control duration               | 150 s    | **150.0 s** | ✅ PASS |
| Minimum TTC (emergency phase)  | —        | 1.29 s      | Emergency braking engaged as designed |

### 3.4 Timeline Highlights

* **t = 0.0 s** – Cruise mode, `a_cmd` saturates at `+3.0 m/s²`; ego accelerates linearly.
* **t ≈ 10.0 s** – Ego reaches 30 m/s; command drops to 0 with no overshoot.
* **t = 30.0 s** – Lead vehicle enters detection at 52.1 m and 25.4 m/s → transition to **follow**; brief deceleration to match lead speed.
* **t ≈ 40–70 s** – Quasi-steady following at ~25 m/s with distance held within ~0.1 m of the 47.5 m safe headway.
* **t ≈ 75–100 s** – Lead accelerates above 30 m/s; ego caps at set speed, distance grows (physically unavoidable, not a controller error).
* **t = 120.0 s** – Lead brakes hard to ~5 m/s, TTC crosses 3 s → **emergency** engaged, `a_cmd = -8.0 m/s²`; minimum distance 9.36 m — collision avoided.
* **t = 130.0 s** – Lead out of range → back to **cruise**, ego recovers to 30 m/s.

### 3.5 Artefacts Produced

* `pid_controller.py` — PID class.
* `acc_system.py` — `AdaptiveCruiseControl` mode logic.
* `simulation.py` — 150 s vehicle simulator.
* `tune.py` — offline gain search (development-time utility).
* `tuning_results.yaml` — final PID gains loaded by `simulation.py`.
* `simulation_results.csv` — 1501-row output log (`time, ego_speed, acceleration_cmd, mode, distance_error, distance, ttc`).
* `acc_report.md` — this report.

All required performance targets are met.
