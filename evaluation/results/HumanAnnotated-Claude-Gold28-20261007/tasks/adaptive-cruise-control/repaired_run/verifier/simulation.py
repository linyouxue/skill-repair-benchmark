"""Run 150s ACC simulation using tuned PID gains."""

import math
import pandas as pd
import yaml

from acc_system import AdaptiveCruiseControl


def load_config():
    with open('vehicle_params.yaml', 'r') as f:
        config = yaml.safe_load(f)
    with open('tuning_results.yaml', 'r') as f:
        tuned = yaml.safe_load(f)
    config['pid_speed'] = tuned['pid_speed']
    config['pid_distance'] = tuned['pid_distance']
    return config


def compute_ttc(distance, ego_speed, lead_speed):
    if distance is None or lead_speed is None:
        return None
    rel = ego_speed - lead_speed
    if rel <= 0 or distance <= 0:
        return None
    return distance / rel


def run_simulation(config, sensor_df):
    dt = config['simulation']['dt']
    max_a = config['vehicle']['max_acceleration']
    min_a = config['vehicle']['max_deceleration']

    acc = AdaptiveCruiseControl(config)

    ego_speed = 0.0
    sim_distance = None  # simulated inter-vehicle distance
    prev_lead_present = False

    results = []
    for i, row in sensor_df.iterrows():
        t = row['time']
        lead_speed = None if pd.isna(row['lead_speed']) else float(row['lead_speed'])
        sensor_distance = None if pd.isna(row['distance']) else float(row['distance'])

        # Initialize / reset simulated distance on lead vehicle transitions
        lead_present = lead_speed is not None
        if lead_present and not prev_lead_present:
            sim_distance = sensor_distance
        elif not lead_present:
            sim_distance = None
        prev_lead_present = lead_present

        accel_cmd, mode, dist_err = acc.compute(ego_speed, lead_speed, sim_distance, dt)
        accel_cmd = max(min_a, min(max_a, accel_cmd))

        ttc = compute_ttc(sim_distance, ego_speed, lead_speed)

        results.append({
            'time': round(t, 2),
            'ego_speed': ego_speed,
            'acceleration_cmd': accel_cmd,
            'mode': mode,
            'distance_error': dist_err,
            'distance': sim_distance,
            'ttc': ttc,
        })

        # Update dynamics for next step
        ego_speed = ego_speed + accel_cmd * dt
        if ego_speed < 0.0:
            ego_speed = 0.0

        if sim_distance is not None and lead_speed is not None:
            sim_distance = sim_distance + (lead_speed - results[-1]['ego_speed']) * dt
            if sim_distance < 0.0:
                sim_distance = 0.0

    return pd.DataFrame(results)


def main():
    config = load_config()
    sensor_df = pd.read_csv('sensor_data.csv')
    results = run_simulation(config, sensor_df)
    results.to_csv('simulation_results.csv', index=False)
    print(f"Wrote {len(results)} rows to simulation_results.csv")


if __name__ == '__main__':
    main()
