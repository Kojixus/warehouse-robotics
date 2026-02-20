import numpy as np
import pandas as pd

STATE_ALIASES = {"CHARGING": "CHARGE"}
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


def _empty_alerts() -> pd.DataFrame:
    return pd.DataFrame(columns=ALERT_COLUMNS)


def _normalize_logs(robot_logs: pd.DataFrame) -> pd.DataFrame:
    required = {"robot_id", "timestamp_min", "state", "duration_min"}
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


def _expand_to_minutes(robot_logs: pd.DataFrame, shift_minutes: int):
    util_diff = np.zeros(shift_minutes + 1, dtype=int)
    charge_diff = np.zeros(shift_minutes + 1, dtype=int)
    fault_diff = np.zeros(shift_minutes + 1, dtype=int)

    for row in robot_logs.itertuples(index=False):
        start = int(getattr(row, "timestamp_min"))
        dur = int(getattr(row, "duration_min"))
        state = str(getattr(row, "state"))

        if dur <= 0:
            continue
        start = max(0, start)
        end = min(shift_minutes, start + dur)
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
        return _empty_alerts()

    df = _normalize_logs(robot_logs)
    if df.empty:
        return _empty_alerts()

    robot_ids = df["robot_id"].unique().tolist()
    fleet_size = max(1, len(robot_ids))

    util, charging, _faults = _expand_to_minutes(df, shift_minutes)

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

    # Fleet rolling utilization alert
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

    # Fleet fault starts over 60-minute window
    faults_df = df[df["state"] == "FAULT"]
    fault_starts = np.zeros(shift_minutes, dtype=int)
    if not faults_df.empty:
        ts = faults_df["timestamp_min"].to_numpy()
        ts = ts[(ts >= 0) & (ts < shift_minutes)]
        if ts.size:
            fault_starts += np.bincount(ts, minlength=shift_minutes)
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

    # Charging congestion
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

    # Robot repeat faults
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

    # Low battery at end of work blocks
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

    # Long idle streaks
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
        return _empty_alerts()

    severity_rank = {"CRIT": 0, "WARN": 1, "INFO": 2}
    out["severity_rank"] = out["severity"].map(severity_rank).fillna(9).astype(int)
    out = (
        out.sort_values(["severity_rank", "timestamp_min", "alert_type"])
        .drop(columns=["severity_rank"])
        .reset_index(drop=True)
    )
    return out[ALERT_COLUMNS]
