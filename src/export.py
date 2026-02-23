from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "export_files.json"

DEFAULT_EXPORT_FILE_NAMES: dict[str, dict[str, dict[str, str]]] = {
    "pick_path": {
        "reports": {
            "kpi_comparison": "output/reports/kpi_comparison.csv",
            "pick_path_report": "output/reports/pick_path_report.html",
        },
        "charts": {
            "route_baseline": "output/charts/route_baseline.png",
            "route_nearest_neighbor": "output/charts/route_nearest_neighbor.png",
            "route_zone_batch": "output/charts/route_zone_batch.png",
        },
    },
    "slotting": {
        "reports": {
            "abc_summary": "output/reports/abc_summary.csv",
            "move_list_top50": "output/reports/move_list_top50.csv",
            "slotting_kpis": "output/reports/slotting_kpis.csv",
        },
        "charts": {
            "heatmap_slotting_before": "output/charts/heatmap_slotting_before.png",
            "heatmap_slotting_after": "output/charts/heatmap_slotting_after.png",
            "heatmap_slotting_delta": "output/charts/heatmap_slotting_delta.png",
            "heatmap_slotting_impact": "output/charts/heatmap_slotting_impact.png",
        },
    },
    "operations": {
        "data": {
            "robot_logs_ops": "output/operations_data/simulated/robot_logs.csv",
            "robot_logs_legacy": "output/control_tower_data/simulated/robot_logs.csv",
            "robot_logs_canonical": "data/simulated/robot_logs.csv",
        },
        "reports": {
            "fleet_daily_kpis": "output/reports/fleet_daily_kpis.csv",
            "robot_kpis": "output/reports/robot_kpis.csv",
            "alerts": "output/reports/alerts.csv",
            "ops_brief": "output/reports/ops_brief.md",
        },
        "charts": {
            "utilization_over_time": "output/charts/utilization_over_time.png",
            "faults_over_time": "output/charts/faults_over_time.png",
        },
    },
    "audit_ready": {
        "data": {
            "inventory_snapshot": "data/simulated/inventory_snapshot.csv",
            "cycle_counts": "data/simulated/cycle_counts.csv",
        },
        "reports": {
            "inventory_accuracy": "output/reports/inventory_accuracy.csv",
            "cycle_count_results": "output/reports/cycle_count_results.csv",
            "exceptions": "output/reports/exceptions.csv",
            "exception_resolution_sla": "output/reports/exception_resolution_sla.csv",
        },
        "audit": {
            "evidence_index": "output/audit/evidence_index.md",
            "run_manifest": "output/audit/run_manifest.json",
        },
    },
    "scenarios": {
        "reports": {
            "scenario_definitions": "output/reports/scenario_definitions.csv",
            "scenario_monte_carlo": "output/reports/scenario_monte_carlo.csv",
            "scenario_summary": "output/reports/scenario_summary.csv",
            "scenario_risk_report": "output/reports/scenario_risk_report.md",
        },
        "charts": {
            "sla_breach_probability": "output/charts/sla_breach_probability.png",
            "cycle_time_p95": "output/charts/cycle_time_p95_by_scenario.png",
            "throughput": "output/charts/throughput_by_scenario.png",
        },
    },
    "portfolio": {
        "pages": {
            "dashboard": "output/portfolio/dashboard.html",
            "credits": "output/portfolio/credits.html",
        }
    },
}


def load_export_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Missing export config file: {resolved_path}")
    with resolved_path.open("r", encoding="utf-8") as file:
        config = json.load(file)
    if not isinstance(config, dict):
        raise ValueError("Export config must be a JSON object")
    return config


def write_export_config(path: Path = DEFAULT_CONFIG_PATH, overwrite: bool = False) -> Path:
    resolved_path = Path(path)
    if resolved_path.exists() and not overwrite:
        raise FileExistsError(
            f"Export config already exists: {resolved_path}. Use --overwrite to replace."
        )
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    with resolved_path.open("w", encoding="utf-8") as file:
        json.dump(DEFAULT_EXPORT_FILE_NAMES, file, indent=2)
        file.write("\n")
    return resolved_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a config file listing export file names."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to write the export file names config.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the config file if it already exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        path = write_export_config(path=args.path, overwrite=args.overwrite)
    except FileExistsError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    print(f"Wrote export config: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
