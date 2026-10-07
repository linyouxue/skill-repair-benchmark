"""PID controller for feedback control loops."""


class PIDController:
    def __init__(self, kp, ki, kd):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.integral = 0.0
        self.prev_error = 0.0
        self._has_prev = False

    def reset(self):
        self.integral = 0.0
        self.prev_error = 0.0
        self._has_prev = False

    def compute(self, error, dt):
        p_term = self.kp * error

        self.integral += error * dt
        i_term = self.ki * self.integral

        if self._has_prev and dt > 0:
            derivative = (error - self.prev_error) / dt
        else:
            derivative = 0.0
        d_term = self.kd * derivative

        self.prev_error = error
        self._has_prev = True

        return p_term + i_term + d_term
