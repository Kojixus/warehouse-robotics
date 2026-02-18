import numpy as np
import pandas as pd

STATE_ALIASES = {"CHARGING": "CHARGE"}
STATE_COLUMNS = ["WORK", "IDLE", "CHARGE", "FAULT"]


def _empty_outputs(shift_minutes: int):
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


def _normalize_logs(robot_logs: pd.DataFrame) -> pd.DataFrame:
    required = {"robot_id", "state", "duration_min"}
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
    return df


def compute_kpis(robot_logs: pd.DataFrame, shift_minutes: int = 480):
    if shift_minutes <= 0:
        raise ValueError("shift_minutes must be > 0.")

    if robot_logs.empty:
        return _empty_outputs(shift_minutes)

    df = _normalize_logs(robot_logs)
    if df.empty:
        return _empty_outputs(shift_minutes)

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
