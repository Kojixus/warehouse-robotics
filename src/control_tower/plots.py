import os
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "output"
CHARTS_DIR = OUTPUT_DIR / "charts"

MPL_CONFIG_DIR = OUTPUT_DIR / ".matplotlib"
os.makedirs(MPL_CONFIG_DIR, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))

import matplotlib.pyplot as plt

STATE_ALIASES = {"CHARGING": "CHARGE"}


def _normalize_logs(robot_logs: pd.DataFrame) -> pd.DataFrame:
    required = {"robot_id", "timestamp_min", "duration_min", "state"}
    missing = required - set(robot_logs.columns)
    if missing:
        raise ValueError(f"robot_logs missing required columns: {sorted(missing)}")

    df = robot_logs.copy()
    df["robot_id"] = df["robot_id"].astype(str)
    df["timestamp_min"] = (
        pd.to_numeric(df["timestamp_min"], errors="coerce").fillna(0).astype(int)
    )
    df["duration_min"] = (
        pd.to_numeric(df["duration_min"], errors="coerce")
        .fillna(0)
        .clip(lower=0)
        .astype(int)
    )
    df["state"] = df["state"].astype(str).str.upper().replace(STATE_ALIASES)
    return df


def _expand_minutes(robot_logs: pd.DataFrame, shift_minutes: int):
    robot_ids = robot_logs["robot_id"].unique().tolist()
    fleet_size = max(1, len(robot_ids))

    work_diff = np.zeros(shift_minutes + 1, dtype=int)
    fault_diff = np.zeros(shift_minutes + 1, dtype=int)

    for row in robot_logs.itertuples(index=False):
        start = max(0, int(row.timestamp_min))
        duration = int(row.duration_min)
        state = str(row.state)

        if duration <= 0:
            continue
        end = min(shift_minutes, start + duration)
        if start >= shift_minutes or end <= start:
            continue

        if state == "WORK":
            work_diff[start] += 1
            work_diff[end] -= 1
        elif state == "FAULT":
            fault_diff[start] += 1
            fault_diff[end] -= 1

    work = np.cumsum(work_diff[:-1])
    faults = np.cumsum(fault_diff[:-1])
    util_pct = (work / fleet_size) * 100.0
    return util_pct, faults


def make_charts(robot_logs: pd.DataFrame, shift_minutes: int = 480):
    if shift_minutes <= 0:
        raise ValueError("shift_minutes must be > 0.")

    os.makedirs(CHARTS_DIR, exist_ok=True)

    if robot_logs.empty:
        util_pct = np.zeros(shift_minutes, dtype=float)
        faults = np.zeros(shift_minutes, dtype=int)
    else:
        df = _normalize_logs(robot_logs)
        util_pct, faults = _expand_minutes(df, shift_minutes)

    x = np.arange(shift_minutes)

    plt.figure(figsize=(10, 4))
    plt.plot(x, util_pct, color="#1f77b4", linewidth=1.8)
    plt.title("Fleet Utilization Over Time (minute-level)")
    plt.xlabel("Minute of shift")
    plt.ylabel("Utilization (%)")
    plt.ylim(0, 100)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "utilization_over_time.png", dpi=200)
    plt.close()

    plt.figure(figsize=(10, 4))
    plt.plot(x, faults, color="#d62728", linewidth=1.8)
    plt.title("Fleet Faults Over Time (robots in FAULT per minute)")
    plt.xlabel("Minute of shift")
    plt.ylabel("Robots in FAULT")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "faults_over_time.png", dpi=200)
    plt.close()
