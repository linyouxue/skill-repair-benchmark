"""Discrete-time PID controller with optional output clamping."""


class PIDController:
    def __init__(self, kp, ki, kd, output_min=None, output_max=None):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self.integral = 0.0
        self.prev_error = 0.0
        self._initialized = False

    def reset(self):
        self.integral = 0.0
        self.prev_error = 0.0
        self._initialized = False

    def compute(self, error, dt):
        p_term = self.kp * error

        self.integral += error * dt
        i_term = self.ki * self.integral

        if self._initialized and dt > 0:
            derivative = (error - self.prev_error) / dt
        else:
            derivative = 0.0
        d_term = self.kd * derivative

        self.prev_error = error
        self._initialized = True

        output = p_term + i_term + d_term

        # Anti-windup via back-calculation: if clamped, undo integration
        unclamped = output
        if self.output_min is not None and output < self.output_min:
            output = self.output_min
        if self.output_max is not None and output > self.output_max:
            output = self.output_max
        if output != unclamped and self.ki != 0:
            self.integral -= error * dt

        return float(output)
