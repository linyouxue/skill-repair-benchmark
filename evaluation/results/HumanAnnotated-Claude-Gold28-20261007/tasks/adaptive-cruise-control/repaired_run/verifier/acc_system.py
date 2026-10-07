"""Adaptive Cruise Control (ACC) system."""

from pid_controller import PIDController


class AdaptiveCruiseControl:
    def __init__(self, config):
        acc = config['acc_settings']
        veh = config['vehicle']

        self.set_speed = acc['set_speed']
        self.time_headway = acc['time_headway']
        self.min_distance = acc['min_distance']
        self.emergency_ttc = acc['emergency_ttc_threshold']

        self.max_accel = veh['max_acceleration']
        self.max_decel = veh['max_deceleration']

        ps = config['pid_speed']
        pd = config['pid_distance']
        self.speed_pid = PIDController(ps['kp'], ps['ki'], ps['kd'])
        self.distance_pid = PIDController(pd['kp'], pd['ki'], pd['kd'])

        self.prev_mode = None

    def _safe_distance(self, ego_speed):
        return ego_speed * self.time_headway + self.min_distance

    def _ttc(self, distance, ego_speed, lead_speed):
        rel = ego_speed - lead_speed
        if rel <= 0 or distance <= 0:
            return None
        return distance / rel

    def _select_mode(self, lead_speed, distance, ego_speed):
        if lead_speed is None or distance is None:
            return 'cruise'
        ttc = self._ttc(distance, ego_speed, lead_speed)
        if ttc is not None and ttc < self.emergency_ttc:
            return 'emergency'
        return 'follow'

    def compute(self, ego_speed, lead_speed, distance, dt):
        mode = self._select_mode(lead_speed, distance, ego_speed)

        if mode != self.prev_mode:
            if mode == 'cruise':
                self.distance_pid.reset()
            elif mode == 'follow':
                self.speed_pid.reset()
            elif mode == 'emergency':
                self.speed_pid.reset()
                self.distance_pid.reset()
        self.prev_mode = mode

        if mode == 'cruise':
            error = self.set_speed - ego_speed
            accel = self.speed_pid.compute(error, dt)
            distance_error = None
        elif mode == 'emergency':
            accel = self.max_decel
            distance_error = distance - self._safe_distance(ego_speed)
        else:  # follow
            safe = self._safe_distance(ego_speed)
            distance_error = distance - safe
            accel = self.distance_pid.compute(distance_error, dt)

        accel = max(self.max_decel, min(self.max_accel, accel))
        return accel, mode, distance_error
