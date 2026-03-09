import os
import random
from pathlib import Path
from typing import Optional

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
STATE_COLUMNS = ["WORK", "IDLE", "CHARGE", "FAULT"]
ALERT_COLUMNS = [
    "timestamp_min",
    "severity",
    "alert_type",
    "robot_id",
    "metric",
    "value",
    "threshold",
    "message",
]
EVENT_COLUMNS = [
    "event_id",
    "timestamp_min",
    "robot_id",
    "state",
    "duration_min",
    "task_type",
    "order_id",
    "battery_pct_start",
    "battery_pct_end",
    "fault_code",
]


def empty_outputs(shift_minutes: int):
    by_robot = pd.DataFrame(
        columns=[
            "robot_id",
            "WORK",
            "IDLE",
            "CHARGE",
            "FAULT",
            "total_min",
            "utilization_pct",
            "downtime_pct",
            "charging_pct",
            "work_events",
            "tasks_per_hour_proxy",
            "fault_events",
            "mttr_min",
        ]
    )
    fleet_daily = pd.DataFrame(
        [
            {
                "fleet_size": 0,
                "shift_minutes": int(shift_minutes),
                "work_min_total": 0,
                "idle_min_total": 0,
                "charge_min_total": 0,
                "fault_min_total": 0,
                "utilization_pct": 0.0,
                "downtime_pct": 0.0,
                "charging_pct": 0.0,
                "tasks_per_hour_proxy": 0.0,
                "faults_per_robot": 0.0,
                "mttr_min": 0.0,
            }
        ]
    )
    return fleet_daily, by_robot


def empty_alerts() -> pd.DataFrame:
    return pd.DataFrame(columns=ALERT_COLUMNS)


def normalize_logs(
    robot_logs: pd.DataFrame, require_timestamp: bool = True
) -> pd.DataFrame:
    required = {"robot_id", "state", "duration_min"}
    if require_timestamp:
        required.add("timestamp_min")

    missing = required - set(robot_logs.columns)
    if missing:
        raise ValueError(f"robot_logs missing required columns: {sorted(missing)}")

    df = robot_logs.copy()
    df["robot_id"] = df["robot_id"].astype(str)
    df["state"] = df["state"].astype(str).str.upper().replace(STATE_ALIASES)
    df["duration_min"] = (
        pd.to_numeric(df["duration_min"], errors="coerce")
        .fillna(0)
        .clip(lower=0)
        .astype(int)
    )
    if "timestamp_min" in df.columns:
        df["timestamp_min"] = (
            pd.to_numeric(df["timestamp_min"], errors="coerce").fillna(0).astype(int)
        )
    return df


def compute_kpis(robot_logs: pd.DataFrame, shift_minutes: int = 480):
    if shift_minutes <= 0:
        raise ValueError("shift_minutes must be > 0.")

    if robot_logs.empty:
        return empty_outputs(shift_minutes)

    df = normalize_logs(robot_logs, require_timestamp=False)
    if df.empty:
        return empty_outputs(shift_minutes)

    durations = df.pivot_table(
        index="robot_id",
        columns="state",
        values="duration_min",
        aggfunc="sum",
        fill_value=0,
    ).reindex(columns=STATE_COLUMNS, fill_value=0)
    durations = durations.astype(int)
    durations["total_min"] = durations.sum(axis=1)

    with np.errstate(divide="ignore", invalid="ignore"):
        durations["utilization_pct"] = np.where(
            durations["total_min"] > 0,
            durations["WORK"] / durations["total_min"] * 100.0,
            0.0,
        )
        durations["downtime_pct"] = np.where(
            durations["total_min"] > 0,
            durations["FAULT"] / durations["total_min"] * 100.0,
            0.0,
        )
        durations["charging_pct"] = np.where(
            durations["total_min"] > 0,
            durations["CHARGE"] / durations["total_min"] * 100.0,
            0.0,
        )

    work_events = df["state"].eq("WORK").groupby(df["robot_id"]).sum().astype(int)
    fault_events = df["state"].eq("FAULT").groupby(df["robot_id"]).sum().astype(int)
    mttr = df[df["state"] == "FAULT"].groupby("robot_id")["duration_min"].mean()

    by_robot = durations.join(work_events.rename("work_events"), how="left")
    by_robot = by_robot.join(fault_events.rename("fault_events"), how="left")
    by_robot = by_robot.join(mttr.rename("mttr_min"), how="left")
    by_robot[["work_events", "fault_events"]] = (
        by_robot[["work_events", "fault_events"]].fillna(0).astype(int)
    )
    by_robot["mttr_min"] = by_robot["mttr_min"].fillna(0.0).astype(float)
    by_robot["tasks_per_hour_proxy"] = by_robot["work_events"] / (shift_minutes / 60.0)

    by_robot = by_robot.reset_index().sort_values("robot_id").reset_index(drop=True)
    by_robot = by_robot[
        [
            "robot_id",
            "WORK",
            "IDLE",
            "CHARGE",
            "FAULT",
            "total_min",
            "utilization_pct",
            "downtime_pct",
            "charging_pct",
            "work_events",
            "tasks_per_hour_proxy",
            "fault_events",
            "mttr_min",
        ]
    ]

    fleet_daily = pd.DataFrame(
        [
            {
                "fleet_size": int(by_robot.shape[0]),
                "shift_minutes": int(shift_minutes),
                "work_min_total": int(by_robot["WORK"].sum()),
                "idle_min_total": int(by_robot["IDLE"].sum()),
                "charge_min_total": int(by_robot["CHARGE"].sum()),
                "fault_min_total": int(by_robot["FAULT"].sum()),
                "utilization_pct": float(by_robot["utilization_pct"].mean()),
                "downtime_pct": float(by_robot["downtime_pct"].mean()),
                "charging_pct": float(by_robot["charging_pct"].mean()),
                "tasks_per_hour_proxy": float(by_robot["tasks_per_hour_proxy"].mean()),
                "faults_per_robot": float(by_robot["fault_events"].mean()),
                "mttr_min": float(by_robot["mttr_min"].mean()),
            }
        ]
    )
    return fleet_daily, by_robot


def expand_alert_minutes(robot_logs: pd.DataFrame, shift_minutes: int):
    util_diff = np.zeros(shift_minutes + 1, dtype=int)
    charge_diff = np.zeros(shift_minutes + 1, dtype=int)
    fault_diff = np.zeros(shift_minutes + 1, dtype=int)

    for row in robot_logs.itertuples(index=False):
        start = int(getattr(row, "timestamp_min"))
        duration = int(getattr(row, "duration_min"))
        state = str(getattr(row, "state"))

        if duration <= 0:
            continue
        start = max(0, start)
        end = min(shift_minutes, start + duration)
        if start >= shift_minutes or end <= start:
            continue

        if state == "WORK":
            util_diff[start] += 1
            util_diff[end] -= 1
        elif state == "CHARGE":
            charge_diff[start] += 1
            charge_diff[end] -= 1
        elif state == "FAULT":
            fault_diff[start] += 1
            fault_diff[end] -= 1

    util = np.cumsum(util_diff[:-1])
    charging = np.cumsum(charge_diff[:-1])
    faults = np.cumsum(fault_diff[:-1])
    return util, charging, faults


def generate_alerts(robot_logs: pd.DataFrame, shift_minutes: int = 480):
    if shift_minutes <= 0:
        raise ValueError("shift_minutes must be > 0.")
    if robot_logs.empty:
        return empty_alerts()

    df = normalize_logs(robot_logs, require_timestamp=True)
    if df.empty:
        return empty_alerts()

    robot_ids = df["robot_id"].unique().tolist()
    fleet_size = max(1, len(robot_ids))

    util, charging, _faults = expand_alert_minutes(df, shift_minutes)

    alerts = []
    cooldown = {}

    def fire(
        ts: int,
        severity: str,
        alert_type: str,
        robot_id: str,
        metric: str,
        value: float,
        threshold: float,
        message: str,
        cooldown_min: int = 30,
    ) -> None:
        key = f"{alert_type}|{robot_id or 'FLEET'}"
        last = cooldown.get(key)
        if last is not None and ts - last < cooldown_min:
            return
        cooldown[key] = ts
        alerts.append(
            {
                "timestamp_min": int(ts),
                "severity": severity,
                "alert_type": alert_type,
                "robot_id": robot_id,
                "metric": metric,
                "value": float(value),
                "threshold": float(threshold),
                "message": message,
            }
        )

    util_pct = (util / fleet_size) * 100.0
    util_window = 30
    if shift_minutes >= util_window:
        util_roll = pd.Series(util_pct).rolling(
            window=util_window, min_periods=util_window
        ).mean()
        for minute in range(util_window - 1, shift_minutes):
            value = util_roll.iloc[minute]
            if np.isnan(value):
                continue
            if value < 55.0:
                fire(
                    ts=minute,
                    severity="CRIT",
                    alert_type="FLEET_LOW_UTIL_30M",
                    robot_id="",
                    metric="utilization_rolling_30m_pct",
                    value=value,
                    threshold=55.0,
                    message="Fleet utilization below threshold for a 30-minute window.",
                    cooldown_min=30,
                )

    faults_df = df[df["state"] == "FAULT"]
    fault_starts = np.zeros(shift_minutes, dtype=int)
    if not faults_df.empty:
        timestamps = faults_df["timestamp_min"].to_numpy()
        timestamps = timestamps[(timestamps >= 0) & (timestamps < shift_minutes)]
        if timestamps.size:
            fault_starts += np.bincount(timestamps, minlength=shift_minutes)
    if shift_minutes >= 60:
        fault_roll = pd.Series(fault_starts).rolling(window=60, min_periods=60).sum()
        for minute in range(59, shift_minutes):
            value = fault_roll.iloc[minute]
            if np.isnan(value):
                continue
            if value > 2.0:
                fire(
                    ts=minute,
                    severity="WARN",
                    alert_type="FLEET_HIGH_FAULT_RATE_60M",
                    robot_id="",
                    metric="fault_starts_rolling_60m",
                    value=value,
                    threshold=2.0,
                    message="High fleet fault rate in the last 60 minutes.",
                    cooldown_min=30,
                )

    charging_pct = (charging / fleet_size) * 100.0
    for minute, value in enumerate(charging_pct):
        if value > 30.0:
            fire(
                ts=minute,
                severity="WARN",
                alert_type="FLEET_CHARGING_CONGESTION",
                robot_id="",
                metric="robots_charging_pct",
                value=value,
                threshold=30.0,
                message="More than 30% of fleet charging simultaneously.",
                cooldown_min=30,
            )

    for robot_id, count in faults_df.groupby("robot_id").size().items():
        if int(count) >= 2:
            fire(
                ts=shift_minutes - 1,
                severity="CRIT",
                alert_type="ROBOT_REPEAT_FAULTS_SHIFT",
                robot_id=str(robot_id),
                metric="fault_events",
                value=float(count),
                threshold=2.0,
                message="Robot had 2+ fault events this shift.",
                cooldown_min=9999,
            )

    if "battery_pct_end" in df.columns:
        work_df = df[df["state"] == "WORK"].copy()
        work_df["battery_pct_end"] = pd.to_numeric(
            work_df["battery_pct_end"], errors="coerce"
        )
        low_battery = work_df[work_df["battery_pct_end"] < 15.0]
        for row in low_battery.itertuples(index=False):
            fire(
                ts=int(row.timestamp_min),
                severity="WARN",
                alert_type="ROBOT_LOW_BATTERY",
                robot_id=str(row.robot_id),
                metric="battery_pct_end",
                value=float(row.battery_pct_end),
                threshold=15.0,
                message="Robot ended WORK block below battery threshold.",
                cooldown_min=45,
            )

    sorted_df = df.sort_values(["robot_id", "timestamp_min"]).reset_index(drop=True)
    for robot_id, group in sorted_df.groupby("robot_id", sort=False):
        idle_streak = 0
        streak_start = -1
        for row in group.itertuples(index=False):
            state = str(row.state)
            duration = int(row.duration_min)
            timestamp = int(row.timestamp_min)

            if state == "IDLE":
                if idle_streak == 0:
                    streak_start = timestamp
                idle_streak += duration
                if idle_streak >= 45:
                    fire(
                        ts=streak_start if streak_start >= 0 else timestamp,
                        severity="WARN",
                        alert_type="ROBOT_LONG_IDLE",
                        robot_id=str(robot_id),
                        metric="idle_streak_min",
                        value=float(idle_streak),
                        threshold=45.0,
                        message="Robot idle streak exceeded threshold.",
                        cooldown_min=60,
                    )
                    idle_streak = 0
                    streak_start = -1
            else:
                idle_streak = 0
                streak_start = -1

    out = pd.DataFrame(alerts)
    if out.empty:
        return empty_alerts()

    severity_rank = {"CRIT": 0, "WARN": 1, "INFO": 2}
    out["severity_rank"] = out["severity"].map(severity_rank).fillna(9).astype(int)
    out = (
        out.sort_values(["severity_rank", "timestamp_min", "alert_type"])
        .drop(columns=["severity_rank"])
        .reset_index(drop=True)
    )
    return out[ALERT_COLUMNS]


def build_demand_curve(orders: pd.DataFrame, shift_minutes: int) -> np.ndarray:
    if shift_minutes <= 0:
        return np.zeros(0, dtype=float)

    demand = np.zeros(shift_minutes, dtype=float)
    if "order_time" in orders.columns:
        times = pd.to_numeric(orders["order_time"], errors="coerce").dropna().astype(int)
        if not times.empty:
            clipped = times.clip(lower=0, upper=shift_minutes - 1).to_numpy()
            demand += np.bincount(clipped, minlength=shift_minutes)[:shift_minutes]
        else:
            demand[:] = 1.0
    else:
        demand[:] = 1.0

    window = min(15, shift_minutes)
    if window > 1:
        kernel = np.ones(window, dtype=float) / float(window)
        smooth = np.convolve(demand, kernel, mode="same")
    else:
        smooth = demand

    max_value = float(smooth.max()) if smooth.size else 0.0
    return smooth / max_value if max_value > 0 else np.zeros(shift_minutes, dtype=float)


def choose_duration(state: str, rng: random.Random) -> int:
    ranges = {
        "WORK": (3, 12),
        "IDLE": (4, 16),
        "CHARGE": (6, 20),
        "FAULT": (4, 14),
    }
    low, high = ranges.get(state, (4, 10))
    return rng.randint(low, high)


def simulate_robot_logs(
    orders: pd.DataFrame,
    locations: pd.DataFrame,
    shift_minutes: int = 480,
    fleet_size: int = 10,
    random_seed: int = 42,
    seed: Optional[int] = None,
) -> pd.DataFrame:
    del locations

    if shift_minutes <= 0:
        return pd.DataFrame(columns=EVENT_COLUMNS)
    if fleet_size <= 0:
        raise ValueError("fleet_size must be > 0.")

    resolved_seed = random_seed if seed is None else seed
    rng = random.Random(resolved_seed)
    np_rng = np.random.default_rng(resolved_seed)

    demand_curve = build_demand_curve(orders, shift_minutes)
    if "order_id" in orders.columns:
        order_ids = orders["order_id"].dropna().astype(str).unique().tolist()
    else:
        order_ids = []
    if not order_ids:
        order_ids = ["ORD0000"]

    robot_ids = [f"R{idx:02d}" for idx in range(1, fleet_size + 1)]
    battery = {robot_id: rng.randint(55, 100) for robot_id in robot_ids}
    cursor_min = {robot_id: 0 for robot_id in robot_ids}

    work_drain_per_minute = (1.1, 2.4)
    idle_drain_per_minute = (0.15, 0.55)
    charge_gain_per_minute = (3.5, 8.0)
    fault_drain_per_minute = (0.1, 0.4)
    fault_codes = ("NAV_ERROR", "MECH_FAILURE", "SENSOR_ISSUE", "BATTERY_LOW")

    logs = []

    def choose_state(robot_id: str, minute: int) -> str:
        level = battery[robot_id]
        demand = float(demand_curve[minute]) if minute < shift_minutes else 0.0

        if level <= 20:
            return "CHARGE"

        work_prob = 0.20 + 0.70 * demand
        if level < 40:
            work_prob -= 0.25
        elif level > 85 and demand < 0.20:
            work_prob -= 0.15

        work_prob = min(0.95, max(0.05, work_prob))
        return "WORK" if rng.random() < work_prob else "IDLE"

    while True:
        robot_id = min(cursor_min, key=cursor_min.get)
        start_min = cursor_min[robot_id]
        if start_min >= shift_minutes:
            break

        state = choose_state(robot_id, start_min)
        duration_min = min(choose_duration(state, rng), shift_minutes - start_min)
        if duration_min <= 0:
            cursor_min[robot_id] = shift_minutes
            continue

        battery_start = int(battery[robot_id])
        battery_end = battery_start
        task_type = state
        order_id = ""
        fault_code = ""

        if state == "WORK":
            task_type = "PICK"
            order_id = rng.choice(order_ids)
            drain = np_rng.uniform(*work_drain_per_minute) * duration_min
            battery_end = max(0, int(round(battery_start - drain)))
        elif state == "CHARGE":
            gain = np_rng.uniform(*charge_gain_per_minute) * duration_min
            battery_end = min(100, int(round(battery_start + gain)))
        else:
            drain = np_rng.uniform(*idle_drain_per_minute) * duration_min
            battery_end = max(0, int(round(battery_start - drain)))

        battery[robot_id] = battery_end
        logs.append(
            {
                "timestamp_min": start_min,
                "robot_id": robot_id,
                "state": state,
                "duration_min": duration_min,
                "task_type": task_type,
                "order_id": order_id,
                "battery_pct_start": battery_start,
                "battery_pct_end": battery_end,
                "fault_code": fault_code,
            }
        )
        cursor_min[robot_id] = start_min + duration_min

        if state != "WORK" or cursor_min[robot_id] >= shift_minutes:
            continue

        demand_factor = float(demand_curve[start_min]) if start_min < shift_minutes else 0.0
        fault_prob = 0.02 + demand_factor * 0.03
        if battery_end < 25:
            fault_prob += 0.04

        if rng.random() >= fault_prob:
            continue

        fault_start = cursor_min[robot_id]
        fault_duration = min(choose_duration("FAULT", rng), shift_minutes - fault_start)
        if fault_duration <= 0:
            continue

        fault_battery_start = int(battery[robot_id])
        fault_drain = np_rng.uniform(*fault_drain_per_minute) * fault_duration
        fault_battery_end = max(0, int(round(fault_battery_start - fault_drain)))
        battery[robot_id] = fault_battery_end

        logs.append(
            {
                "timestamp_min": fault_start,
                "robot_id": robot_id,
                "state": "FAULT",
                "duration_min": fault_duration,
                "task_type": "",
                "order_id": "",
                "battery_pct_start": fault_battery_start,
                "battery_pct_end": fault_battery_end,
                "fault_code": rng.choice(fault_codes),
            }
        )
        cursor_min[robot_id] = fault_start + fault_duration

    if not logs:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    out = pd.DataFrame(logs).sort_values(["timestamp_min", "robot_id"]).reset_index(drop=True)
    out["event_id"] = [f"E{idx:06d}" for idx in range(1, len(out) + 1)]
    return out[EVENT_COLUMNS]


def expand_plot_minutes(robot_logs: pd.DataFrame, shift_minutes: int):
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
        df = normalize_logs(robot_logs, require_timestamp=True)
        util_pct, faults = expand_plot_minutes(df, shift_minutes)

    minutes = np.arange(shift_minutes)

    plt.figure(figsize=(10, 4))
    plt.plot(minutes, util_pct, color="#1f77b4", linewidth=1.8)
    plt.title("Fleet Utilization Over Time (minute-level)")
    plt.xlabel("Minute of shift")
    plt.ylabel("Utilization (%)")
    plt.ylim(0, 100)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "utilization_over_time.png", dpi=200)
    plt.close()

    plt.figure(figsize=(10, 4))
    plt.plot(minutes, faults, color="#d62728", linewidth=1.8)
    plt.title("Fleet Faults Over Time (robots in FAULT per minute)")
    plt.xlabel("Minute of shift")
    plt.ylabel("Robots in FAULT")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "faults_over_time.png", dpi=200)
    plt.close()


def render_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "_No data._"
    try:
        return df.to_markdown(index=False)
    except Exception:
        return "```\n" + df.to_string(index=False) + "\n```"


def write_ops_brief(
    out_path: str,
    fleet_daily: pd.DataFrame,
    by_robot: pd.DataFrame,
    alerts: pd.DataFrame,
    shift_minutes: int = 480,
):
    out_file = Path(out_path)
    os.makedirs(out_file.parent, exist_ok=True)

    fleet_row = (
        fleet_daily.iloc[0].to_dict()
        if fleet_daily is not None and not fleet_daily.empty
        else {}
    )
    by_robot = by_robot.copy() if by_robot is not None else pd.DataFrame()

    if not by_robot.empty and "utilization_pct" in by_robot.columns:
        worst = by_robot.sort_values("utilization_pct", ascending=True).head(1)
        best = by_robot.sort_values("utilization_pct", ascending=False).head(1)
    else:
        worst = pd.DataFrame()
        best = pd.DataFrame()

    top_alerts = alerts.head(5) if alerts is not None and not alerts.empty else pd.DataFrame()

    lines = [
        "# Daily Robotics Ops Brief - Simulated Shift",
        "",
        f"- Shift length: **{shift_minutes} minutes**",
        f"- Fleet size: **{int(fleet_row.get('fleet_size', 0))} robots**",
        "",
        "## Executive Summary",
        "",
        f"- Fleet utilization (avg): **{fleet_row.get('utilization_pct', 0):.1f}%**",
        (
            f"- Downtime (avg): **{fleet_row.get('downtime_pct', 0):.1f}%** | "
            f"Charging (avg): **{fleet_row.get('charging_pct', 0):.1f}%**"
        ),
        (
            f"- Faults per robot: **{fleet_row.get('faults_per_robot', 0):.2f}** | "
            f"MTTR: **{fleet_row.get('mttr_min', 0):.1f} min**"
        ),
        (
            "- Throughput proxy (tasks/hour/robot): "
            f"**{fleet_row.get('tasks_per_hour_proxy', 0):.2f}**"
        ),
        "",
        "## KPI Summary (Fleet)",
        "",
        render_table(fleet_daily),
        "",
        "## KPI Summary (By Robot)",
        "",
        render_table(by_robot),
        "",
        "## Top Alerts",
        "",
        render_table(top_alerts) if not top_alerts.empty else "- No alerts triggered.",
        "",
        "## Notable Robots",
        "",
    ]

    if not worst.empty:
        row = worst.iloc[0]
        lines.append(
            f"- Lowest utilization: **{row['robot_id']}** at **{row['utilization_pct']:.1f}%** "
            f"(faults: {int(row.get('fault_events', 0))}, "
            f"charging: {row.get('charging_pct', 0):.1f}%)"
        )
    if not best.empty:
        row = best.iloc[0]
        lines.append(
            f"- Highest utilization: **{row['robot_id']}** at **{row['utilization_pct']:.1f}%** "
            f"(faults: {int(row.get('fault_events', 0))}, "
            f"charging: {row.get('charging_pct', 0):.1f}%)"
        )
    if worst.empty and best.empty:
        lines.append("- No per-robot KPI data available.")

    lines.extend(
        [
            "",
            "## Root Cause Hypotheses (Simulated)",
            "",
            "- Low utilization windows may indicate demand troughs, charging overlap, or repeated fault recoveries.",
            "- Elevated fault rate may reflect navigation/obstacle issues, battery degradation, or comms instability.",
            "- High simultaneous charging may suggest insufficient charger capacity or poor charge scheduling.",
            "",
            "## Recommended Actions",
            "",
            "- Stagger charge cycles to avoid charging congestion.",
            "- Review top fault codes and add mitigation playbooks.",
            "- Balance dispatching across robots to reduce long idle streaks.",
            "",
        ]
    )

    with out_file.open("w", encoding="utf-8") as file_obj:
        file_obj.write("\n".join(lines))


DATA_DIR = PROJECT_ROOT / "data" / "simulated"
OPERATIONS_DIR = OUTPUT_DIR / "operations_data"
LEGACY_CONTROL_TOWER_DIR = OUTPUT_DIR / "control_tower_data"
SIMULATED_DIR = OPERATIONS_DIR / "simulated"
LEGACY_SIMULATED_DIR = LEGACY_CONTROL_TOWER_DIR / "simulated"
REPORTS_DIR = OUTPUT_DIR / "reports"
CANONICAL_LOG_PATH = DATA_DIR / "robot_logs.csv"

SHIFT_MINUTES = 480
FLEET_SIZE = 10
RANDOM_SEED = 42


def ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(SIMULATED_DIR, exist_ok=True)
    os.makedirs(LEGACY_SIMULATED_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(CHARTS_DIR, exist_ok=True)


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


def run_operations(
    shift_minutes: int = SHIFT_MINUTES,
    fleet_size: int = FLEET_SIZE,
    random_seed: int = RANDOM_SEED,
) -> dict[str, Path]:
    ensure_dirs()

    orders = read_csv_flexible(resolve_input_path("orders.csv"))
    locations = read_csv_flexible(resolve_input_path("locations.csv"))

    robot_logs = simulate_robot_logs(
        orders=orders,
        locations=locations,
        shift_minutes=shift_minutes,
        fleet_size=fleet_size,
        random_seed=random_seed,
    )
    robot_logs.to_csv(SIMULATED_DIR / "robot_logs.csv", index=False)
    robot_logs.to_csv(LEGACY_SIMULATED_DIR / "robot_logs.csv", index=False)
    robot_logs.to_csv(CANONICAL_LOG_PATH, index=False)

    fleet_daily, by_robot = compute_kpis(robot_logs, shift_minutes=shift_minutes)
    fleet_daily.to_csv(REPORTS_DIR / "fleet_daily_kpis.csv", index=False)
    by_robot.to_csv(REPORTS_DIR / "robot_kpis.csv", index=False)

    alerts = generate_alerts(robot_logs, shift_minutes=shift_minutes)
    alerts.to_csv(REPORTS_DIR / "alerts.csv", index=False)

    write_ops_brief(
        out_path=str(REPORTS_DIR / "ops_brief.md"),
        fleet_daily=fleet_daily,
        by_robot=by_robot,
        alerts=alerts,
        shift_minutes=shift_minutes,
    )
    make_charts(robot_logs, shift_minutes=shift_minutes)

    return {
        "simulated_logs": SIMULATED_DIR / "robot_logs.csv",
        "legacy_simulated_logs": LEGACY_SIMULATED_DIR / "robot_logs.csv",
        "canonical_logs": CANONICAL_LOG_PATH,
        "fleet_kpis": REPORTS_DIR / "fleet_daily_kpis.csv",
        "robot_kpis": REPORTS_DIR / "robot_kpis.csv",
        "alerts": REPORTS_DIR / "alerts.csv",
        "ops_brief": REPORTS_DIR / "ops_brief.md",
        "util_chart": CHARTS_DIR / "utilization_over_time.png",
        "fault_chart": CHARTS_DIR / "faults_over_time.png",
    }


def main() -> None:
    outputs = run_operations()

    print("DONE: Operations outputs generated")
    print(
        f" - {outputs['simulated_logs'].relative_to(PROJECT_ROOT).as_posix()}"
    )
    print(
        f" - {outputs['legacy_simulated_logs'].relative_to(PROJECT_ROOT).as_posix()}"
    )
    print(f" - {outputs['canonical_logs'].relative_to(PROJECT_ROOT).as_posix()}")
    print(f" - {outputs['fleet_kpis'].relative_to(PROJECT_ROOT).as_posix()}")
    print(f" - {outputs['robot_kpis'].relative_to(PROJECT_ROOT).as_posix()}")
    print(f" - {outputs['alerts'].relative_to(PROJECT_ROOT).as_posix()}")
    print(f" - {outputs['ops_brief'].relative_to(PROJECT_ROOT).as_posix()}")
    print(f" - {outputs['util_chart'].relative_to(PROJECT_ROOT).as_posix()}")
    print(f" - {outputs['fault_chart'].relative_to(PROJECT_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
