"""Adaptive Cruise Control system with cruise/follow/emergency modes."""

from pid_controller import PIDController


class AdaptiveCruiseControl:
    def __init__(self, config):
        veh = config['vehicle']
        acc = config['acc_settings']
        pid_s = config['pid_speed']
        pid_d = config['pid_distance']

        self.max_accel = veh['max_acceleration']
        self.max_decel = veh['max_deceleration']
        self.set_speed = acc['set_speed']
        self.time_headway = acc['time_headway']
        self.min_distance = acc['min_distance']
        self.ttc_threshold = acc['emergency_ttc_threshold']

        self.speed_pid = PIDController(
            pid_s['kp'], pid_s['ki'], pid_s['kd'],
            output_min=self.max_decel, output_max=self.max_accel,
        )
        self.distance_pid = PIDController(
            pid_d['kp'], pid_d['ki'], pid_d['kd'],
            output_min=self.max_decel, output_max=self.max_accel,
        )

        self._prev_mode = None

    def _safe_distance(self, ego_speed):
        return ego_speed * self.time_headway + self.min_distance

    @staticmethod
    def _ttc(distance, ego_speed, lead_speed):
        rel = ego_speed - lead_speed
        if rel <= 0 or distance <= 0:
            return None
        return distance / rel

    def compute(self, ego_speed, lead_speed, distance, dt):
        # No lead vehicle -> cruise control on set speed
        if lead_speed is None or distance is None:
            if self._prev_mode != 'cruise':
                self.speed_pid.reset()
                self.distance_pid.reset()
            self._prev_mode = 'cruise'
            error = self.set_speed - ego_speed
            accel = self.speed_pid.compute(error, dt)
            return accel, 'cruise', None

        ttc = self._ttc(distance, ego_speed, lead_speed)
        distance_error = distance - self._safe_distance(ego_speed)

        # Emergency mode: apply maximum deceleration
        if ttc is not None and ttc < self.ttc_threshold:
            if self._prev_mode != 'emergency':
                self.speed_pid.reset()
                self.distance_pid.reset()
            self._prev_mode = 'emergency'
            return self.max_decel, 'emergency', distance_error

        # Follow mode: use distance PID, but do not exceed set-speed cruise
        if self._prev_mode != 'follow':
            self.distance_pid.reset()
            self.speed_pid.reset()
        self._prev_mode = 'follow'

        accel_dist = self.distance_pid.compute(distance_error, dt)
        # Cap by cruise controller so we never exceed set_speed while following
        speed_err = self.set_speed - ego_speed
        accel_cruise = self.speed_pid.kp * speed_err  # simple P cap
        accel = min(accel_dist, accel_cruise)
        accel = max(self.max_decel, min(self.max_accel, accel))

        return accel, 'follow', distance_error
