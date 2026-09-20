"""Run the ACC simulation using PID gains loaded from tuning_results.yaml."""

import pandas as pd
import yaml

from acc_system import AdaptiveCruiseControl


def load_config(params_path='vehicle_params.yaml', tuning_path='tuning_results.yaml'):
    with open(params_path, 'r') as f:
        config = yaml.safe_load(f)
    with open(tuning_path, 'r') as f:
        tuning = yaml.safe_load(f)
    # Override PID gains with tuned values
    config['pid_speed'] = tuning['pid_speed']
    config['pid_distance'] = tuning['pid_distance']
    return config


def run_simulation(config, sensor_df):
    dt = config['simulation']['dt']
    max_accel = config['vehicle']['max_acceleration']
    max_decel = config['vehicle']['max_deceleration']

    acc = AdaptiveCruiseControl(config)

    ego_speed = 0.0
    sim_distance = None  # Simulated distance to lead vehicle
    prev_lead_present = False
    results = []

    for _, row in sensor_df.iterrows():
        t = row['time']
        lead_speed = None if pd.isna(row['lead_speed']) else float(row['lead_speed'])
        sensor_distance = None if pd.isna(row['distance']) else float(row['distance'])

        lead_present = lead_speed is not None and sensor_distance is not None
        # Initialise simulated distance when lead first (re)appears
        if lead_present and not prev_lead_present:
            sim_distance = sensor_distance
        if not lead_present:
            sim_distance = None
        prev_lead_present = lead_present

        accel_cmd, mode, distance_error = acc.compute(
            ego_speed, lead_speed, sim_distance, dt
        )

        if mode == 'cruise' or sim_distance is None or lead_speed is None:
            ttc_log = None
            dist_log = None
            derr_log = None
        else:
            rel = ego_speed - lead_speed
            ttc_log = sim_distance / rel if rel > 0 and sim_distance > 0 else None
            dist_log = sim_distance
            derr_log = distance_error

        results.append({
            'time': round(t, 2),
            'ego_speed': round(ego_speed, 4),
            'acceleration_cmd': round(accel_cmd, 4),
            'mode': mode,
            'distance_error': None if derr_log is None else round(derr_log, 4),
            'distance': None if dist_log is None else round(dist_log, 4),
            'ttc': None if ttc_log is None else round(ttc_log, 4),
        })

        # Integrate ego dynamics
        accel_cmd = max(max_decel, min(max_accel, accel_cmd))
        ego_speed = max(0.0, ego_speed + accel_cmd * dt)

        # Integrate simulated inter-vehicle distance
        if sim_distance is not None and lead_speed is not None:
            sim_distance = sim_distance + (lead_speed - ego_speed) * dt

    return pd.DataFrame(results)


def main():
    config = load_config()
    sensor_df = pd.read_csv('sensor_data.csv')
    results = run_simulation(config, sensor_df)
    results.to_csv('simulation_results.csv', index=False)
    print(f"Wrote {len(results)} rows to simulation_results.csv")


if __name__ == '__main__':
    main()
