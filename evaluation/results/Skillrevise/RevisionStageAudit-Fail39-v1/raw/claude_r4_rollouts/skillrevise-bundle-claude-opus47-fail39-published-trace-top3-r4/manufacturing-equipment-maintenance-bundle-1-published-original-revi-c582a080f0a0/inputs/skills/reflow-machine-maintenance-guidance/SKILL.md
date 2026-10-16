# Reflow Machine Maintenance Guidance

## Purpose
Answer reflow equipment maintenance questions by extracting rules and thresholds from a reflow handbook and cross-validating them against MES, thermocouple, and defect datasets, producing the task-declared JSON outputs on time.

## When to Use
Trigger when a task provides a reflow handbook plus tabular process data and asks for per-run metrics (ramp, TAL, peak margin, conveyor feasibility) or maintenance recommendations with explicit output files.

## Procedure
- Discover inputs. List the data directory (e.g., `/app/data`) and the output directory (e.g., `/app/output`). Record exact file names for handbook PDF, `mes_log.csv`, `thermocouples.csv`, and any defect table. If any required input is missing, stop and report; do not fabricate values.
- Extract handbook. Try PDF text extraction in a bounded fallback chain, stopping at first success: `pdfplumber` -> `pypdf` -> `pymupdf` (`fitz`) -> `pdftotext` CLI. Spend at most one step on tool discovery. If all fail, continue with cfg values set to `null` and surface the gap in the output.
- Build cfg from handbook text. Populate: `preheat_region` ({type: temp_band|zone_band|time_band, ...}), `ramp_limit_c_per_s`, `tal_threshold_c_source` (or explicit `tal_threshold_c`), `tal_min_s`, `tal_max_s`, `peak_margin_c`, conveyor rule (`L_eff_cm`, `t_min_s`, `t_max_s`). If the handbook gives multiple values, keep the stricter one; if ambiguous, record both and apply the stricter in computation.
- Load and normalize data. Read CSVs; cast `run_id`, `tc_id` to str; sort thermocouples by `(run_id, tc_id, time_s)`. Skip segments where `dt <= 0`.
- Compute per question using the equations below. For each run, reduce TCs: max metric -> `(max_value, smallest_tc_id)`; min metric -> `(min_value, smallest_tc_id)`.
- Write outputs. For each required question, write the task-declared JSON file to the task-declared output path. Round numeric fields to 2 decimals. Sort rows by `run_id` (or `board_family` where applicable). Write all required files even if some fields are `null`.
- Verify. Reload each written file with `json.load`; assert file exists, parses, and contains the declared top-level keys. Log the list of written files before finishing. ## Equations (compute checkpoint)
- Segment slope: `s_i = (T_i - T_{i-1}) / (t_i - t_{i-1})`, `dt > 0`.
- Region max ramp: `max(s_i)` restricted to segments where both endpoints meet the region predicate (`temp_band`, `zone_band`, or `time_band`).
- Time above threshold: linear interpolation at crossings; sum durations where `T > thr`.
- Peak: `peak_tc = max(temp_c)`; `min_peak_run = min(peak_tc)`; `required_peak = liquidus + peak_margin_c`.
- Conveyor: `speed_max = (L_eff_cm / t_min_s) * 60`; `speed_min = (L_eff_cm / t_max_s) * 60`. ## Config Schema ``` cfg = { "preheat_region": {"type": "temp_band|zone_band|time_band", ...}, "ramp_limit_c_per_s": float | null, "tal_threshold_c": float | null, "tal_min_s": float | null, "tal_max_s": float | null, "peak_margin_c": float | null, "conveyor": {"L_eff_cm": float, "t_min_s": float, "t_max_s": float} | null } ```

## Constraints / Pitfalls
- Do not spend more than one step on PDF tool discovery; use the fallback chain and move on.
- Do not switch output paths; write exactly to the task-declared paths. If a write fails, inspect permissions rather than silently relocating.
- Do not skip writing any required output; emit the file with `null` fields and a short `notes` entry if handbook values could not be extracted.
- Do not guess handbook numbers; cite the extracted text or set `null`.
- Do not include long conceptual prose in outputs; outputs must match the declared schema only.
- Always sort thermocouple samples before slope/TAL math; always break ties on reductions with smallest `tc_id`.
- Final step must be the verify checkpoint: list output directory and `json.load` each produced file before claiming completion.