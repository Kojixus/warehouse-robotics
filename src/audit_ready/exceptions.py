import random

import pandas as pd


EXCEPTION_COLUMNS = [
    "exception_id",
    "order_id",
    "sku",
    "location_id",
    "exception_type",
    "severity",
    "created_time_min",
    "resolved_time_min",
    "sla_target_min",
    "status",
    "owner_role",
    "notes",
    "resolution_time_min",
    "within_sla",
]


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _robot_fault_pressure(robot_logs: pd.DataFrame) -> set[int]:
    """
    Returns a set of high fault-pressure minutes.
    Minute is marked when >=2 robots are in FAULT simultaneously.
    """
    if robot_logs is None or robot_logs.empty:
        return set()

    required = {"state", "timestamp_min", "duration_min"}
    if not required.issubset(set(robot_logs.columns)):
        return set()

    shift_minutes = 480
    diff = [0] * (shift_minutes + 1)

    fault_rows = robot_logs[robot_logs["state"].astype(str).str.upper() == "FAULT"]
    for row in fault_rows.itertuples(index=False):
        start = max(0, _to_int(getattr(row, "timestamp_min", 0), 0))
        dur = max(0, _to_int(getattr(row, "duration_min", 0), 0))
        end = min(shift_minutes, start + dur)
        if end <= start:
            continue
        diff[start] += 1
        diff[end] -= 1

    pressure = set()
    active_faults = 0
    for minute in range(shift_minutes):
        active_faults += diff[minute]
        if active_faults >= 2:
            pressure.add(minute)

    return pressure


def generate_exceptions(
    orders: pd.DataFrame,
    inventory_snapshot: pd.DataFrame,
    robot_logs: pd.DataFrame = None,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Creates a realistic exceptions log:
      - SHORT_PICK (inventory available < ordered qty)
      - DAMAGED
      - LOCATION_BLOCKED
      - ROBOT_DELAY (if order_time occurs during fault pressure window)
    """
    if orders is None or orders.empty:
        return pd.DataFrame(columns=EXCEPTION_COLUMNS)

    rng = random.Random(seed)

    inv = inventory_snapshot[["sku", "available_qty"]].copy()
    inv["sku"] = inv["sku"].astype(str)
    inv["available_qty"] = pd.to_numeric(inv["available_qty"], errors="coerce").fillna(0).astype(int)
    inv_map = dict(zip(inv["sku"], inv["available_qty"]))

    fault_pressure_minutes = _robot_fault_pressure(robot_logs)

    rows = []
    exc_i = 0

    # Base probabilities (tune for realism; not too noisy)
    p_damaged = 0.008
    p_loc_blocked = 0.006

    for order in orders.itertuples(index=False):
        order_id = str(getattr(order, "order_id", ""))
        sku = str(getattr(order, "sku", ""))
        loc = str(getattr(order, "pick_location_id", ""))
        qty = max(1, _to_int(getattr(order, "qty", 1), 1))
        order_time = _to_int(getattr(order, "order_time", rng.randint(0, 470)), rng.randint(0, 470))
        order_time = min(479, max(0, order_time))

        # ROBOT_DELAY: if we have robot logs and order falls in pressure window
        if order_time in fault_pressure_minutes and rng.random() < 0.20:
            exc_i += 1
            created = order_time
            sla = 45
            resolved = min(479, created + rng.randint(10, 80))
            rows.append(
                {
                    "exception_id": f"EXC{str(exc_i).zfill(5)}",
                    "order_id": order_id,
                    "sku": sku,
                    "location_id": loc,
                    "exception_type": "ROBOT_DELAY",
                    "severity": "WARN",
                    "created_time_min": created,
                    "resolved_time_min": resolved,
                    "sla_target_min": sla,
                    "status": "CLOSED",
                    "owner_role": "ops_supervisor",
                    "notes": "Order delayed due to elevated robot fault pressure window.",
                }
            )

        # SHORT_PICK: if available inventory is less than qty
        avail = int(inv_map.get(sku, 0))
        if avail < qty and rng.random() < 0.85:
            exc_i += 1
            created = min(479, max(0, order_time + rng.randint(0, 25)))
            sla = 120
            resolved = min(479, created + rng.randint(20, 180))
            rows.append(
                {
                    "exception_id": f"EXC{str(exc_i).zfill(5)}",
                    "order_id": order_id,
                    "sku": sku,
                    "location_id": loc,
                    "exception_type": "SHORT_PICK",
                    "severity": "CRIT",
                    "created_time_min": created,
                    "resolved_time_min": resolved,
                    "sla_target_min": sla,
                    "status": "CLOSED",
                    "owner_role": "inventory_control",
                    "notes": "Pick short due to insufficient available inventory; requires investigation/adjustment.",
                }
            )
            continue

        # Simulate successful picks consuming available inventory.
        inv_map[sku] = max(0, avail - qty)

        # DAMAGED
        if rng.random() < p_damaged:
            exc_i += 1
            created = min(479, max(0, order_time + rng.randint(0, 30)))
            sla = 90
            resolved = min(479, created + rng.randint(10, 140))
            rows.append(
                {
                    "exception_id": f"EXC{str(exc_i).zfill(5)}",
                    "order_id": order_id,
                    "sku": sku,
                    "location_id": loc,
                    "exception_type": "DAMAGED",
                    "severity": "WARN",
                    "created_time_min": created,
                    "resolved_time_min": resolved,
                    "sla_target_min": sla,
                    "status": "CLOSED",
                    "owner_role": "qa",
                    "notes": "Unit damaged; re-pick or replace required.",
                }
            )

        # LOCATION_BLOCKED
        if rng.random() < p_loc_blocked:
            exc_i += 1
            created = min(479, max(0, order_time + rng.randint(0, 15)))
            sla = 60
            resolved = min(479, created + rng.randint(5, 100))
            rows.append(
                {
                    "exception_id": f"EXC{str(exc_i).zfill(5)}",
                    "order_id": order_id,
                    "sku": sku,
                    "location_id": loc,
                    "exception_type": "LOCATION_BLOCKED",
                    "severity": "WARN",
                    "created_time_min": created,
                    "resolved_time_min": resolved,
                    "sla_target_min": sla,
                    "status": "CLOSED",
                    "owner_role": "floor_lead",
                    "notes": "Location temporarily inaccessible (congestion/obstruction); reroute or clear.",
                }
            )

    out = pd.DataFrame.from_records(rows)
    if out.empty:
        return pd.DataFrame(columns=EXCEPTION_COLUMNS)

    out["created_time_min"] = pd.to_numeric(out["created_time_min"], errors="coerce").fillna(0).astype(int)
    out["resolved_time_min"] = pd.to_numeric(out["resolved_time_min"], errors="coerce").fillna(0).astype(int)
    out["sla_target_min"] = pd.to_numeric(out["sla_target_min"], errors="coerce").fillna(0).astype(int)

    out["resolution_time_min"] = (out["resolved_time_min"] - out["created_time_min"]).clip(lower=0)
    out["within_sla"] = out["resolution_time_min"] <= out["sla_target_min"]

    out = out.sort_values(["created_time_min", "severity"], ascending=[True, False]).reset_index(drop=True)
    return out.reindex(columns=EXCEPTION_COLUMNS)


def summarize_exception_sla(exceptions: pd.DataFrame) -> pd.DataFrame:
    if exceptions is None or exceptions.empty:
        return pd.DataFrame(
            columns=["exception_type", "count", "pct_within_sla", "avg_resolution_min", "sla_breaches"]
        )

    df = exceptions.copy()
    if "resolution_time_min" not in df.columns:
        df["created_time_min"] = pd.to_numeric(df["created_time_min"], errors="coerce").fillna(0).astype(int)
        df["resolved_time_min"] = pd.to_numeric(df["resolved_time_min"], errors="coerce").fillna(0).astype(int)
        df["resolution_time_min"] = (df["resolved_time_min"] - df["created_time_min"]).clip(lower=0)

    if "within_sla" not in df.columns:
        df["sla_target_min"] = pd.to_numeric(df["sla_target_min"], errors="coerce").fillna(0).astype(int)
        df["within_sla"] = df["resolution_time_min"] <= df["sla_target_min"]

    df["within_sla"] = df["within_sla"].astype(bool)

    summary = (
        df.groupby("exception_type", dropna=False)
        .agg(
            count=("exception_type", "size"),
            within_sla_count=("within_sla", "sum"),
            avg_resolution_min=("resolution_time_min", "mean"),
        )
        .reset_index()
    )

    summary["pct_within_sla"] = (summary["within_sla_count"] / summary["count"] * 100.0).round(2)
    summary["avg_resolution_min"] = summary["avg_resolution_min"].astype(float).round(2)
    summary["sla_breaches"] = (summary["count"] - summary["within_sla_count"]).astype(int)

    return (
        summary[["exception_type", "count", "pct_within_sla", "avg_resolution_min", "sla_breaches"]]
        .sort_values(["sla_breaches", "count"], ascending=[False, False])
        .reset_index(drop=True)
    )
