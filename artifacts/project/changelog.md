# Changelog

All notable changes to this project will be documented in this file.

This project follows a simple semantic versioning approach:

- **MAJOR**: big scope expansion or breaking changes
- **MINOR**: new features/deliverables
- **PATCH**: fixes that don’t change core logic/results

---

## [v1.1] - 2026-02-18

### Added

- Week 2 deliverables for **Pick Path Optimization MVP**:
  - KPI comparison report output (`output/reports/kpi_comparison.csv`)
  - HTML summary report (`output/reports/pick_path_report.html`)
  - Route images for baseline vs heuristics (`output/charts/*.png`)

### Changed

- Updated plotting setup to ensure charts/images generate reliably across environments by setting a writable Matplotlib config directory _before_ importing `matplotlib.pyplot`:
  - `MPL_CONFIG_DIR = os.path.join("output", ".matplotlib")`
  - `os.makedirs(MPL_CONFIG_DIR, exist_ok=True)`
  - `os.environ.setdefault("MPLCONFIGDIR", MPL_CONFIG_DIR)`
  - `import matplotlib.pyplot as plt`

### Fixed

- Prevented runtime issues where Matplotlib fails to write cache/config files in restricted or non-writable environments (e.g., sandbox/CI/locked-down systems), which could block generation of Week 2 route images and reports.

### Notes

- No changes were made to input data schemas (`locations.csv`, `skus.csv`, `orders.csv`) or to KPI definitions/route heuristics as part of this fix; it only improves plotting reliability.

---

## [v1.0] - 2026-02-17

### Added

- Week 1 deliverables for **Setup + Baseline Simulation + Program Artifacts**:
  - Repository structure and initial documentation (`README.md`)
  - Synthetic datasets:
    - `data/simulated/locations.csv`
    - `data/simulated/skus.csv`
    - `data/simulated/orders.csv`
  - Program artifacts:
    - `artifacts/program/charter.md`
    - `artifacts/program/changelog.md` (initial)
  - Baseline KPI groundwork (distance proxy approach and definitions)

### Notes

- Baseline analysis uses simplified assumptions (2D grid + Manhattan distance) intended for relative comparisons and demo purposes.
