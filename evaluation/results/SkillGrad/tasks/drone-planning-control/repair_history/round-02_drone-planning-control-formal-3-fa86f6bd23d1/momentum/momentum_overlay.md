### [drone-planning-control] Missing required output artifacts under `/root/results/<id>/`
- signal: failure
- pattern: deliverables-generation-loop
- anchor: required-output-file-locations
- gap: The run terminated without executing any implementation/simulation/tuning pipeline that writes the harness-required per-command artifacts. Concretely, there is no creation of `/root/results/*` and no saved files like `/root/results/001/metrics_3d.json`, `tuning_results.json`, `planned_trajectory.npy`, `actual_trajectory.npy`, or plots. This indicates the executor did not perform (or did not complete) the required end-to-end loop “for each command file → parse → plan → simulate → compute metrics → save outputs”.
- proposed_change: Strengthen workflow guidance at `position-controller-trajectory-planner` → `Required Output File Locations` into a mandatory driver procedure: (1) enumerate all command IDs/files, (2) for each ID create `/root/results/<id>/plots/`, (3) run parse_flight_plan → trajectory_planner → closed-loop simulation (position+attitude+motor+dynamics) → stepinfo_3d (settling_threshold=0.02) → plot-quadrotor, (4) save `planned_trajectory.npy`, `actual_trajectory.npy`, `metrics_3d.json`, `tuning_results.json`, and plot PNGs, and (5) add a final verification step that checks file existence/schema for every ID before finishing.

## WORKFLOW-THEMES

- (none this iteration)
