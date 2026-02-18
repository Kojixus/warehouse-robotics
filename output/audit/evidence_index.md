# Audit Evidence Index

- Run ID: **run_20260218T205544Z_a8e2345b**
- Timestamp (UTC): **2026-02-18T20:55:44Z**
- Seed: **42**

## Inputs

- `data/simulated/locations.csv`
- `data/simulated/skus.csv`
- `data/simulated/orders.csv`
- `data/simulated/robot_logs.csv`
- `output/reports/move_list_top50.csv`

## Outputs (Evidence Artifacts)

- **Inventory snapshot:** `data/simulated/inventory_snapshot.csv`
- **Cycle counts:** `data/simulated/cycle_counts.csv`
- **Inventory accuracy summary:** `output/reports/inventory_accuracy.csv`
- **Cycle count results summary:** `output/reports/cycle_count_results.csv`
- **Exceptions log:** `output/reports/exceptions.csv`
- **Exception SLA summary:** `output/reports/exception_resolution_sla.csv`
- **Run manifest:** `output/audit/run_manifest.json`

## What this pack demonstrates

- Inventory snapshot is reproducible and traceable to specific inputs (SKU master, locations, orders).
- Cycle counts quantify variance and provide an accuracy signal for inventory control.
- Exceptions log captures operational disruptions and enables SLA performance reporting.
- Run manifest provides file hashes for evidence integrity and repeatable verification.
