from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable

import pandas as pd

try:
    from .metrics import summarize_runs, summarize_scenarios
    from .plots import plot_cycle_time_p95, plot_sla_breach_probability, plot_throughput
    from .scenario_config import load_config
    from .simulation_model import GlobalParams, ScenarioParams, run_scenario_monte_carlo
except ImportError:
    from metrics import summarize_runs, summarize_scenarios
    from plots import plot_cycle_time_p95, plot_sla_breach_probability, plot_throughput
    from scenario_config import load_config
    from simulation_model import GlobalParams, ScenarioParams, run_scenario_monte_carlo


SCENARIO_COLUMNS = [
    "name",
    "demand_multiplier",
    "robots_available_pct",
    "fault_multiplier",
    "queue_delay_multiplier",
]

ORDERS_COLUMNS = [
    "order_id",
    "order_time",
    "due_time",
    "priority",
    "sku",
    "qty",
    "pick_location_id",
]

LOCATIONS_COLUMNS = ["location_id", "x", "y", "zone", "is_prime"]
ROBOT_LOG_COLUMNS = ["robot_id", "timestamp_min", "state", "duration_min"]


def ensure_dirs() -> None:
    os.makedirs("output/reports", exist_ok=True)
    os.makedirs("output/charts", exist_ok=True)


def _stable_scenario_seed(base_seed: int, scenario_name: str) -> int:
    digest = hashlib.blake2b(scenario_name.encode("utf-8"), digest_size=8).digest()
    offset = int.from_bytes(digest, byteorder="big", signed=False) % 100_000
    return int(base_seed) + offset


def _split_single_column_csv(df: pd.DataFrame) -> pd.DataFrame:
    header = str(df.columns[0])
    cols = [c.strip() for c in header.split(",")]
    series = df.iloc[:, 0].astype(str).str.strip().str.strip('"')
    split = series.str.split(",", expand=True)
    if split.shape[1] != len(cols):
        raise ValueError(
            f"CSV export appears malformed: expected {len(cols)} columns, got {split.shape[1]} after split."
        )
    split.columns = cols
    return split


def read_simulation_csv(path: str, expected_cols: Iterable[str]) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Missing input file: {file_path}")

    df = pd.read_csv(file_path)
    if len(df.columns) == 1 and "," in str(df.columns[0]):
        df = _split_single_column_csv(df)

    missing = set(expected_cols) - set(df.columns)
    if missing:
        raise ValueError(f"{file_path} missing required columns: {sorted(missing)}")

    return df


def resolve_robot_logs_path() -> Path | None:
    candidates = [
        Path("data/simulated/robot_logs.csv"),
        Path("output/control_tower_data/simulated/robot_logs.csv"),
        Path("output/simulated/robot_logs.csv"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def write_risk_report(out_path: str, summary: pd.DataFrame, breach_threshold: float) -> None:
    lines = []
    lines.append("# Scenario Risk Report (Monte Carlo)\n")
    lines.append(f"- SLA breach threshold: **>{breach_threshold:.2f}%**\n")

    if summary.empty:
        lines.append("No results found.\n")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return

    top = summary.head(3)
    lines.append("## Top Risk Scenarios (by probability of SLA breach)\n")
    for _, r in top.iterrows():
        lines.append(
            f"- **{r['scenario']}**: "
            f"P(breach > threshold) **{r['prob_sla_breach_gt_threshold_pct']:.2f}%**, "
            f"avg breach **{r['avg_sla_breach_pct']:.2f}%**, "
            f"avg P95 cycle **{r['avg_p95_cycle_time_min']:.2f} min**"
        )

    lines.append("\n## Summary Table\n")
    try:
        lines.append(summary.to_markdown(index=False))
    except Exception:
        lines.append("`tabulate` is not installed; using CSV-style table fallback.\n")
        lines.append(summary.to_csv(index=False))

    lines.append("\n## Operational Interpretation\n")
    lines.append("- Higher demand increases queueing and pushes orders closer to (or beyond) due times.")
    lines.append("- Reduced robot availability increases wait time via reduced capacity.")
    lines.append("- Higher fault rates add variability and tail risk (worse P95s).")
    lines.append("\n## Recommended Mitigations\n")
    lines.append("- Stagger charging and rebalance dispatching to reduce peak congestion.")
    lines.append("- Add redundancy: minimum fleet availability threshold or manual fallback playbook.")
    lines.append("- Fault hot-spot mitigation: obstacle cleanup, comms checks, and preventive maintenance.\n")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    ensure_dirs()

    cfg = load_config("config/scenarios.json")
    g0 = cfg["global"]

    g = GlobalParams(
        shift_minutes=int(g0["shift_minutes"]),
        base_servers=int(g0["base_servers"]),
        start_x=int(g0["start_x"]),
        start_y=int(g0["start_y"]),
        pick_seconds_per_line=float(g0["pick_seconds_per_line"]),
        travel_seconds_per_unit=float(g0["travel_seconds_per_unit"]),
        base_congestion_mean_min=float(g0["base_congestion_mean_min"]),
        base_congestion_sigma_min=float(g0["base_congestion_sigma_min"]),
        base_fault_prob_per_order=float(g0["base_fault_prob_per_order"]),
        fault_delay_min_min=float(g0["fault_delay_min_min"]),
        fault_delay_max_min=float(g0["fault_delay_max_min"]),
        capacity_penalty_scale_min=float(g0["capacity_penalty_scale_min"]),
        congestion_gain=float(g0["congestion_gain"]),
        fault_prob_gain=float(g0["fault_prob_gain"]),
    )

    breach_threshold = float(g0["sla_breach_threshold_pct"])
    runs = int(g0["monte_carlo_runs"])
    base_seed = int(g0["base_seed"])

    orders = read_simulation_csv("data/simulated/orders.csv", ORDERS_COLUMNS)
    locations = read_simulation_csv("data/simulated/locations.csv", LOCATIONS_COLUMNS)
    robot_logs_path = resolve_robot_logs_path()
    robot_logs = (
        read_simulation_csv(str(robot_logs_path), ROBOT_LOG_COLUMNS)
        if robot_logs_path is not None
        else None
    )
    if robot_logs_path is not None:
        print(f"Using robot logs: {robot_logs_path.as_posix()}")
    else:
        print("Using robot logs: none found (dynamic downtime/congestion/fault pressure disabled)")

    scenario_def = pd.DataFrame(cfg["scenarios"]).loc[:, SCENARIO_COLUMNS]
    scenario_def.to_csv("output/reports/scenario_definitions.csv", index=False)

    per_order_all = []
    for s in cfg["scenarios"]:
        sp = ScenarioParams(
            name=str(s["name"]),
            demand_multiplier=float(s["demand_multiplier"]),
            robots_available_pct=float(s["robots_available_pct"]),
            fault_multiplier=float(s["fault_multiplier"]),
            queue_delay_multiplier=float(s["queue_delay_multiplier"]),
        )

        per_order = run_scenario_monte_carlo(
            orders=orders,
            locations=locations,
            g=g,
            s=sp,
            runs=runs,
            base_seed=_stable_scenario_seed(base_seed, sp.name),
            robot_logs=robot_logs,
        )
        per_order_all.append(per_order)

    per_order_all = pd.concat(per_order_all, axis=0, ignore_index=True)

    monte = summarize_runs(per_order_all, shift_minutes=g.shift_minutes)
    monte.to_csv("output/reports/scenario_monte_carlo.csv", index=False)

    summary = summarize_scenarios(monte, sla_breach_threshold_pct=breach_threshold)
    summary.to_csv("output/reports/scenario_summary.csv", index=False)

    write_risk_report("output/reports/scenario_risk_report.md", summary, breach_threshold)

    plot_sla_breach_probability(summary, "output/charts/sla_breach_probability.png")
    plot_cycle_time_p95(summary, "output/charts/cycle_time_p95_by_scenario.png")
    plot_throughput(summary, "output/charts/throughput_by_scenario.png")

    print("DONE: scenario analysis outputs generated")
    print(" - output/reports/scenario_definitions.csv")
    print(" - output/reports/scenario_monte_carlo.csv")
    print(" - output/reports/scenario_summary.csv")
    print(" - output/reports/scenario_risk_report.md")
    print(" - output/charts/sla_breach_probability.png")
    print(" - output/charts/cycle_time_p95_by_scenario.png")
    print(" - output/charts/throughput_by_scenario.png")


if __name__ == "__main__":
    main()
