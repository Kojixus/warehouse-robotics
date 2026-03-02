# Changelog

All notable changes to this project will be documented in this file.

This project uses a practical semantic versioning approach:

- **MAJOR**: scope expansion or breaking changes
- **MINOR**: new week deliverable(s)
- **PATCH**: fixes, hardening, and validation that do not change intended functionality

---

## [v1.4.4] - 2026-03-02

### Changed

- Switched string literals in `src/audit_ready/audit.py` to single quotes throughout.
- Kept the literal double-quote character uses (`.strip('"')`) as-is since they’re not double-quoted strings.
- Introduced `run_id_timestamp` to avoid mixed quoting in the `run_id` f-string.

---

## [v1.4.3] - 2026-02-20

### Changed

- **Week 4 folder and path rename to Operations**
  - Updated from `src/control_tower/run_control_tower.py` to `src/operations/run_operations.py`.
  - Updated `control_tower` to `operations`.
  - Added backward-compatible : `python main.py control_tower` maps to `operations`.
  - Updated docs/portfolio references to use `src/operations/run_operations.py`.

- **Operations log output path migration**
  - Primary Week 4 output path is now:
    - `output/operations_data/simulated/robot_logs.csv`
  - Legacy compatibility path remains available:
    - `output/control_tower_data/simulated/robot_logs.csv`

- **Timezone standardization to EST**
  - Audit and inventory timestamps now use `EST`.
  - Inventory timestamp fields were updated:
    - `timestamp_est`
    - `snapshot_est`

### Docs

- `README.md` with current pipeline modules, commands, and outputs.
- Added a visual gallery to `README.md` using generated charts from `output/charts/*`.
- Added a dedicated `Credits` section to `README.md` with stack and module attribution.

---

## [v1.4.2] - 2026-02-18

### Changed

- **Scenario stress sensitivity tuning with robot-log coupling**
  - Added new global knobs in `config/scenarios.json`:
    - `capacity_penalty_scale_min`: increased to `12`
    - `congestion_gain`: increased to `1.1`
    - `fault_prob_gain`: increased to `0.35`
  - `src/scenarios/simulation_model.py` now applies minute-level robot log pressure to:
    - capacity penalty (downtime impact on cycle time),
    - congestion amplification (CHARGE/FAULT pressure),
    - dynamic fault probability uplift.
  - `src/scenarios/run_scenarios.py` now auto-loads robot logs from standard/legacy paths and reports which source is used.
  - `src/scenarios/scenario_config.py` now validates the new scenario-global knobs.

---

## [v1.4.1] - 2026-02-18

### Fixed

- **Robot log alignment across pipelines**
  - `src/operations/run_operations.py` now writes robot logs to both:
    - `output/operations_data/simulated/robot_logs.csv`
    - `data/simulated/robot_logs.csv` (canonical path for downstream consumers)
  - `src/audit_ready/run_audit_pack.py` now resolves robot logs from compatible locations:
    - `data/simulated/robot_logs.csv`
    - `output/operations_data/simulated/robot_logs.csv`
    - `output/control_tower_data/simulated/robot_logs.csv` (legacy fallback)
    - `output/simulated/robot_logs.csv` (legacy fallback)
  - Audit evidence inputs now include the resolved robot log file path when present.

---

## [v1.4] - 2026-02-18

### Added

- **Week 5: Audit-Ready Ops Pack (Inventory + Exceptions + Evidence)**
  - Inventory snapshot generation:
    - `data/simulated/inventory_snapshot.csv`
  - Cycle count plan + results:
    - `data/simulated/cycle_counts.csv`
    - `output/reports/cycle_count_results.csv`
  - Inventory accuracy summary:
    - `output/reports/inventory_accuracy.csv`
  - Operational exception logging + SLA rollup:
    - `output/reports/exceptions.csv`
    - `output/reports/exception_resolution_sla.csv`
  - Evidence pack for traceability and reproducibility:
    - `output/audit/run_manifest.json`
    - `output/audit/evidence_index.md`
  - One-command entrypoint for Week 5 evidence generation:
    - `python src/audit_ready/run_audit_pack.py`

### Notes

- Evidence pack is intended to demonstrate traceability (inputs → outputs) and reproducible runs for portfolio purposes.

---

## [v1.3.1] - 2026-02-18

### Fixed

- **Operations reliability hardening**
  - Corrected runtime issues and path mismatches across `src/operations/*`
  - Improved simulator and pipeline entrypoint correctness and determinism
  - Hardened KPI/alerts/ops brief/plot modules for robustness and performance

### Validation

- Completed verification workflow:
  - Import/compile checks for Operations modules
  - End-to-end pipeline execution (log generation → KPIs → alerts → ops brief → charts)
  - Outputs reviewed for completeness and consistency

### Engineering Notes

- Maintenance summary (as recorded): **1 file changed** (**+200 / -160**)

---

## [v1.3] - 2026-02-18

### Added

- **Week 4: Robotics Operations (AMR Fleet Ops)**
  - Simulation log output: `data/simulated/robot_logs.csv`
  - Fleet KPI outputs:
    - `output/reports/fleet_kpis_daily.csv`
    - `output/reports/fleet_kpis_by_robot.csv`
  - Alerting output: `output/reports/alerts.csv`
  - Ops briefing output: `output/reports/ops_brief.md`
  - Operational charts:
    - `output/charts/utilization_over_time.png`
    - `output/charts/faults_over_time.png`
  - One-command entrypoint: `python src/operations/run_operations.py`

### Notes

- Operations simulation is seeded for repeatability and designed as a portfolio-grade operational model (not a production WMS integration).

---

## [v1.2] - 2026-02-18

### Added

- **Week 3: Slotting Optimization (ABC + Move List + Single Impact Heatmap)**
  - ABC classification: `output/reports/abc_summary.csv`
  - Slotting move list: `output/reports/move_list_top50.csv`
  - Slotting KPI summary: `output/reports/slotting_kpis.csv`
  - Single slotting impact visualization:
    - `output/charts/heatmap_slotting_impact.png`
    - Represents **Δ Picks (After − Before)** with **Top 30 absolute changes annotated**

### Changed

- Heatmap axes labeling standardized for warehouse interpretation:
  - X-axis: **Aisle (X)**
  - Y-axis: **Bay (Y)**

### Removed

- Consolidated prior multi-heatmap outputs (Before/After/Delta) into one operational impact view to reduce noise and improve readability on larger grids.

### Notes

- “Current SKU location” baseline is inferred from order history (most frequent pick location per SKU) and documented as a simulation assumption.

---

## [v1.1] - 2026-02-18

### Added

- **Week 2: Pick Path Optimization MVP**
  - KPI comparison output: `output/reports/kpi_comparison.csv`
  - Report output: `output/reports/pick_path_report.html`
  - Route charts:
    - `output/charts/route_baseline.png`
    - `output/charts/route_nearest_neighbor.png`
    - `output/charts/route_zone_batch.png`
  - Enhanced route visualization option: numbered pick sequence overlay (for demo clarity)

### Fixed

- Plot/image generation reliability in restricted/non-writable environments by setting a writable Matplotlib config directory **before** importing pyplot:
  - `MPL_CONFIG_DIR = os.path.join("output", ".matplotlib")`
  - `os.makedirs(MPL_CONFIG_DIR, exist_ok=True)`
  - `os.environ.setdefault("MPLCONFIGDIR", MPL_CONFIG_DIR)`
  - `import matplotlib.pyplot as plt`

### Notes

- No changes to routing heuristics or KPI definitions were introduced by the plotting fix.

---

## [v1.0] - 2026-02-17

### Added

- **Week 1: Setup + Baseline Simulation + Program Artifacts**
  - Repository structure and documentation baseline (`README.md`)
  - Synthetic datasets:
    - `data/simulated/locations.csv`
    - `data/simulated/skus.csv`
    - `data/simulated/orders.csv`
  - Program artifacts:
    - `artifacts/program/charter.md`
    - `artifacts/program/wbs.csv`
    - `artifacts/program/risk_register.csv`
    - `CHANGELOG.md`

### Notes

- Baseline travel model uses a simplified 2D layout with Manhattan equations distance to support relative comparisons and portfolio demonstration.
