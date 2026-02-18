import os
from pathlib import Path

import pandas as pd

try:
    from .alerts import generate_alerts
    from .kpis import compute_kpis
    from .ops_brief import write_ops_brief
    from .plots import make_charts
    from .sim_robot_logs import simulate_robot_logs
except ImportError:
    from alerts import generate_alerts
    from kpis import compute_kpis
    from ops_brief import write_ops_brief
    from plots import make_charts
    from sim_robot_logs import simulate_robot_logs

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "simulated"
OUTPUT_DIR = PROJECT_ROOT / "output"
CONTROL_TOWER_DIR = OUTPUT_DIR / "control_tower_data"
SIMULATED_DIR = CONTROL_TOWER_DIR / "simulated"
REPORTS_DIR = OUTPUT_DIR / "reports"

SHIFT_MINUTES = 480
FLEET_SIZE = 10
RANDOM_SEED = 42


def ensure_dirs() -> None:
    os.makedirs(SIMULATED_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR / "charts", exist_ok=True)


def read_csv_flexible(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if len(df.columns) == 1 and "," in str(df.columns[0]):
        raw = pd.read_csv(path, header=None, dtype=str).iloc[:, 0]
        split = raw.str.split(",", expand=True)
        header = split.iloc[0].tolist()
        df = split.iloc[1:].copy()
        df.columns = header
        df = df.reset_index(drop=True)
    return df  # pyright: ignore[reportReturnType]


def resolve_input_path(name: str) -> Path:
    preferred = DATA_DIR / name
    legacy = SIMULATED_DIR / name
    if preferred.exists():
        return preferred
    if legacy.exists():
        return legacy
    raise FileNotFoundError(
        f"Missing input file '{name}'. Checked '{preferred}' and '{legacy}'."
    )


def main() -> None:
    ensure_dirs()

    orders = read_csv_flexible(resolve_input_path("orders.csv"))
    locations = read_csv_flexible(resolve_input_path("locations.csv"))

    robot_logs = simulate_robot_logs(
        orders=orders,
        locations=locations,
        shift_minutes=SHIFT_MINUTES,
        fleet_size=FLEET_SIZE,
        random_seed=RANDOM_SEED,
    )
    robot_logs.to_csv(SIMULATED_DIR / "robot_logs.csv", index=False)

    fleet_daily, by_robot = compute_kpis(robot_logs, shift_minutes=SHIFT_MINUTES)
    fleet_daily.to_csv(REPORTS_DIR / "fleet_daily_kpis.csv", index=False)
    by_robot.to_csv(REPORTS_DIR / "robot_kpis.csv", index=False)

    alerts = generate_alerts(robot_logs, shift_minutes=SHIFT_MINUTES)
    alerts.to_csv(REPORTS_DIR / "alerts.csv", index=False)

    write_ops_brief(
        out_path=str(REPORTS_DIR / "ops_brief.md"),
        fleet_daily=fleet_daily,
        by_robot=by_robot,
        alerts=alerts,
        shift_minutes=SHIFT_MINUTES,
    )
    make_charts(robot_logs, shift_minutes=SHIFT_MINUTES)

    print("DONE: Control Tower outputs generated")
    print(f" - {SIMULATED_DIR.relative_to(PROJECT_ROOT).as_posix()}/robot_logs.csv")
    print(f" - {REPORTS_DIR.relative_to(PROJECT_ROOT).as_posix()}/fleet_daily_kpis.csv")
    print(f" - {REPORTS_DIR.relative_to(PROJECT_ROOT).as_posix()}/robot_kpis.csv")
    print(f" - {REPORTS_DIR.relative_to(PROJECT_ROOT).as_posix()}/alerts.csv")
    print(f" - {REPORTS_DIR.relative_to(PROJECT_ROOT).as_posix()}/ops_brief.md")
    print(" - output/charts/utilization_over_time.png")
    print(" - output/charts/faults_over_time.png")


if __name__ == "__main__":
    main()
