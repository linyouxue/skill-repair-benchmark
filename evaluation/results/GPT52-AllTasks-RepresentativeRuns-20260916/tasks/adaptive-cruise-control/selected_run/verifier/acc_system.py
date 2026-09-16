from __future__ import annotations

from dataclasses import dataclass

from pid_controller import PIDController


@dataclass(frozen=True)
class VehicleLimits:
    max_acceleration: float
    max_deceleration: float


class AdaptiveCruiseControl:
    def __init__(self, config: dict):
        self.config = config

        acc_cfg = config["acc_settings"]
        veh_cfg = config["vehicle"]

        self.set_speed = float(acc_cfg["set_speed"])
        self.time_headway = float(acc_cfg["time_headway"])
        self.min_distance = float(acc_cfg["min_distance"])
        self.emergency_ttc_threshold = float(acc_cfg["emergency_ttc_threshold"])

        self.limits = VehicleLimits(
            max_acceleration=float(veh_cfg["max_acceleration"]),
            max_deceleration=float(veh_cfg["max_deceleration"]),
        )

        sp = config.get("pid_speed", {})
        dp = config.get("pid_distance", {})

        self.pid_speed = PIDController(sp.get("kp", 0.0), sp.get("ki", 0.0), sp.get("kd", 0.0))
        self.pid_distance = PIDController(dp.get("kp", 0.0), dp.get("ki", 0.0), dp.get("kd", 0.0))

        self.pid_speed.output_min = self.limits.max_deceleration
        self.pid_speed.output_max = self.limits.max_acceleration

        self.pid_distance.output_min = self.limits.max_deceleration
        self.pid_distance.output_max = 0.0

        self._lead_present_prev = False

    def compute(
        self,
        ego_speed: float,
        lead_speed: float | None,
        distance: float | None,
        dt: float,
    ) -> tuple[float, str, float | None]:
        lead_present = lead_speed is not None and distance is not None

        if self._lead_present_prev and not lead_present:
            self.pid_distance.reset()

        if not self._lead_present_prev and lead_present:
            self.pid_distance.reset()

        self._lead_present_prev = lead_present

        if not lead_present:
            speed_ref = self.set_speed
            accel = self.pid_speed.compute(speed_ref - ego_speed, dt)
            return self._clamp_accel(accel), "cruise", None

        desired_gap = ego_speed * self.time_headway + self.min_distance
        spacing_error = float(distance - desired_gap)
        distance_deficit = max(0.0, -spacing_error)

        # Hard safety floor: avoid getting inside the configured minimum gap.
        if distance < self.min_distance:
            self.pid_speed.reset()
            self.pid_distance.reset()
            return self.limits.max_deceleration, "emergency", distance_deficit

        ttc = None
        rel_speed = ego_speed - float(lead_speed)
        if rel_speed > 1e-6 and distance > 0:
            ttc = distance / rel_speed

        if ttc is not None and ttc < self.emergency_ttc_threshold:
            self.pid_speed.reset()
            self.pid_distance.reset()
            return self.limits.max_deceleration, "emergency", distance_deficit

        accel_speed = self.pid_speed.compute(self.set_speed - ego_speed, dt)

        accel = accel_speed
        if spacing_error < 0.0:
            accel_brake = self.pid_distance.compute(spacing_error, dt)
            accel = min(accel_speed, accel_brake)

        return self._clamp_accel(accel), "follow", distance_deficit

    def _clamp_accel(self, accel: float) -> float:
        return float(max(self.limits.max_deceleration, min(self.limits.max_acceleration, accel)))
