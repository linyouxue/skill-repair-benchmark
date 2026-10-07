"""Compute performance metrics on simulation_results.csv for the report."""

import pandas as pd


def rise_time(times, values, target):
    t10 = t90 = None
    for t, v in zip(times, values):
        if t10 is None and v >= 0.1 * target:
            t10 = t
        if t90 is None and v >= 0.9 * target:
            t90 = t
            return t90 - t10
    return None


def overshoot(values, target):
    m = max(values)
    return 0.0 if m <= target else (m - target) / target * 100.0


def settling_time(times, values, target, tol=0.02):
    band = target * tol
    settled = None
    for t, v in zip(times, values):
        if abs(v - target) > band:
            settled = None
        elif settled is None:
            settled = t
    return settled


def main():
    df = pd.read_csv('simulation_results.csv')
    target = 30.0

    # Speed metrics on initial cruise segment (0-30s)
    cruise0 = df[(df['mode'] == 'cruise') & (df['time'] <= 30.0)]
    rt = rise_time(cruise0['time'].tolist(), cruise0['ego_speed'].tolist(), target)
    ov = overshoot(cruise0['ego_speed'].tolist(), target)
    final = cruise0[cruise0['time'] >= 25.0]['ego_speed']
    sse_speed = abs(target - final.mean())
    st = settling_time(cruise0['time'].tolist(), cruise0['ego_speed'].tolist(), target, 0.02)

    print("=== Speed metrics (initial cruise 0-30s) ===")
    print(f"Rise time:       {rt:.2f} s   (target < 10s)")
    print(f"Overshoot:       {ov:.3f} %   (target < 5%)")
    print(f"Settling time:   {st:.2f} s   (2% band)" if st is not None else "Settling time: N/A")
    print(f"SS error:        {sse_speed:.4f} m/s (target < 0.5)")

    # Distance metrics on steady follow segment t=40-70s
    steady = df[(df['time'] >= 40.0) & (df['time'] <= 70.0) & df['distance_error'].notna()]
    sse_dist = steady['distance_error'].abs().mean()
    follow_all = df[df['distance'].notna()]
    min_d = follow_all['distance'].min()
    print()
    print("=== Distance metrics ===")
    print(f"SS error (40-70s): {sse_dist:.3f} m   (target < 2m)")
    print(f"Minimum distance:  {min_d:.2f} m    (target > 5m)")

    # Mode breakdown
    print()
    print("=== Mode breakdown ===")
    print(df['mode'].value_counts().to_string())

    # Final cruise segment check (130-150s)
    cruise1 = df[(df['mode'] == 'cruise') & (df['time'] >= 130.0)]
    if len(cruise1) > 0:
        sse_final = abs(target - cruise1['ego_speed'].mean())
        print(f"\nFinal cruise SS error (130-150s): {sse_final:.4f} m/s")


if __name__ == '__main__':
    main()
