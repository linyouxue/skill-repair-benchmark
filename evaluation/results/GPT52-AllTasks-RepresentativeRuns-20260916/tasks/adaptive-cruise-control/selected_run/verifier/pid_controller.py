from __future__ import annotations


class PIDController:
    def __init__(self, kp: float, ki: float, kd: float):
        self.kp = float(kp)
        self.ki = float(ki)
        self.kd = float(kd)

        self.output_min: float | None = None
        self.output_max: float | None = None

        self.integral = 0.0
        self.prev_error = 0.0

    def reset(self) -> None:
        self.integral = 0.0
        self.prev_error = 0.0

    def compute(self, error: float, dt: float) -> float:
        if dt <= 0:
            dt = 0.0

        p_term = self.kp * error

        d_term = 0.0
        if self.kd != 0.0 and dt > 0.0:
            d_term = self.kd * ((error - self.prev_error) / dt)

        # Propose an integral update, but apply conditional integration
        # to avoid integral windup while still allowing recovery from saturation.
        integral_candidate = self.integral + error * dt
        i_term_candidate = self.ki * integral_candidate

        unclamped = p_term + i_term_candidate + d_term
        output = unclamped

        if self.output_min is not None:
            output = max(self.output_min, output)
        if self.output_max is not None:
            output = min(self.output_max, output)

        if output == unclamped:
            self.integral = integral_candidate
        else:
            # If we're saturated, only integrate if the error would move the
            # controller back toward the unsaturated region.
            integrate = False
            if self.output_max is not None and output >= self.output_max and error < 0:
                integrate = True
            if self.output_min is not None and output <= self.output_min and error > 0:
                integrate = True

            if integrate:
                self.integral = integral_candidate

        self.prev_error = error
        return float(output)
