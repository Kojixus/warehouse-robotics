import random
from typing import Optional

import numpy as np
import pandas as pd

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


def _build_demand_curve(orders: pd.DataFrame, shift_minutes: int) -> np.ndarray:
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


def _choose_duration(state: str, rng: random.Random) -> int:
    ranges = {
        "WORK": (3, 12),
        "IDLE": (4, 16),
        "CHARGE": (6, 20),
        "FAULT": (4, 14),
    }
    lo, hi = ranges.get(state, (4, 10))
    return rng.randint(lo, hi)


def simulate_robot_logs(
    orders: pd.DataFrame,
    locations: pd.DataFrame,
    shift_minutes: int = 480,
    fleet_size: int = 10,
    random_seed: int = 42,
    seed: Optional[int] = None,
) -> pd.DataFrame:
    del locations  # Included for API compatibility and future model extensions.

    if shift_minutes <= 0:
        return pd.DataFrame(columns=EVENT_COLUMNS)
    if fleet_size <= 0:
        raise ValueError("fleet_size must be > 0.")

    resolved_seed = random_seed if seed is None else seed
    rng = random.Random(resolved_seed)
    np_rng = np.random.default_rng(resolved_seed)

    demand_curve = _build_demand_curve(orders, shift_minutes)
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
        duration_min = min(_choose_duration(state, rng), shift_minutes - start_min)
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
        fault_dur = min(_choose_duration("FAULT", rng), shift_minutes - fault_start)
        if fault_dur <= 0:
            continue

        fault_battery_start = int(battery[robot_id])
        fault_drain = np_rng.uniform(*fault_drain_per_minute) * fault_dur
        fault_battery_end = max(0, int(round(fault_battery_start - fault_drain)))
        battery[robot_id] = fault_battery_end

        logs.append(
            {
                "timestamp_min": fault_start,
                "robot_id": robot_id,
                "state": "FAULT",
                "duration_min": fault_dur,
                "task_type": "",
                "order_id": "",
                "battery_pct_start": fault_battery_start,
                "battery_pct_end": fault_battery_end,
                "fault_code": rng.choice(fault_codes),
            }
        )
        cursor_min[robot_id] = fault_start + fault_dur

    if not logs:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    df = pd.DataFrame(logs).sort_values(["timestamp_min", "robot_id"]).reset_index(drop=True)
    df["event_id"] = [f"E{idx:06d}" for idx in range(1, len(df) + 1)]
    return df[EVENT_COLUMNS]
