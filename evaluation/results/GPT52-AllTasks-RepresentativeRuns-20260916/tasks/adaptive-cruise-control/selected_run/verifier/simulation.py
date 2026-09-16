from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import yaml

from acc_system import AdaptiveCruiseControl


def load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run_simulation(
    config_path: str | Path = "vehicle_params.yaml",
    tuning_path: str | Path = "tuning_results.yaml",
    sensor_path: str | Path = "sensor_data.csv",
    output_csv: str | Path = "simulation_results.csv",
) -> pd.DataFrame:
    config = load_yaml(config_path)
    tuning = load_yaml(tuning_path)

    config["pid_speed"] = dict(tuning.get("pid_speed", {}))
    config["pid_distance"] = dict(tuning.get("pid_distance", {}))

    dt_default = float(config.get("simulation", {}).get("dt", 0.1))

    df = pd.read_csv(sensor_path)
    times = df["time"].tolist()

    acc = AdaptiveCruiseControl(config)

    ego_speed = 0.0
    ego_pos = 0.0

    lead_pos: float | None = None

    results: list[dict] = []

    for i, row in df.iterrows():
        t = float(row["time"])
        dt = float(times[i + 1] - t) if i < len(times) - 1 else dt_default

        lead_present = pd.notna(row["lead_speed"]) and pd.notna(row["distance"])
        if lead_present:
            lead_speed = float(row["lead_speed"])
            if lead_pos is None:
                lead_pos = ego_pos + float(row["distance"])
        else:
            lead_speed = None
            lead_pos = None

        distance = None
        if lead_pos is not None:
            distance = float(lead_pos - ego_pos)

        accel_cmd, mode, distance_error = acc.compute(ego_speed, lead_speed, distance, dt)

        ttc = None
        if lead_speed is not None and distance is not None:
            rel_speed = ego_speed - lead_speed
            if rel_speed > 1e-6 and distance > 0.0:
                ttc = distance / rel_speed

        results.append(
            {
                "time": round(t, 10),
                "ego_speed": ego_speed,
                "acceleration_cmd": accel_cmd,
                "mode": mode,
                "distance_error": distance_error,
                "distance": distance,
                "ttc": ttc,
            }
        )

        # Integrate to next step.
        ego_speed = max(0.0, ego_speed + accel_cmd * dt)
        ego_pos = ego_pos + ego_speed * dt

        if lead_pos is not None:
            lead_pos = lead_pos + float(lead_speed) * dt

    out_df = pd.DataFrame(results, columns=[
        "time",
        "ego_speed",
        "acceleration_cmd",
        "mode",
        "distance_error",
        "distance",
        "ttc",
    ])

    def _fmt_num(val: float) -> str:
        s = f"{float(val):.6f}".rstrip("0").rstrip(".")
        return s if "." in s else f"{s}.0"

    # Write with blanks for missing values.
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(out_df.columns.tolist())
        for _, r in out_df.iterrows():
            writer.writerow(
                [
                    f"{r['time']:.1f}",
                    _fmt_num(r["ego_speed"]),
                    _fmt_num(r["acceleration_cmd"]),
                    r["mode"],
                    "" if pd.isna(r["distance_error"]) else _fmt_num(r["distance_error"]),
                    "" if pd.isna(r["distance"]) else _fmt_num(r["distance"]),
                    "" if pd.isna(r["ttc"]) else _fmt_num(r["ttc"]),
                ]
            )

    return out_df


if __name__ == "__main__":
    run_simulation()
