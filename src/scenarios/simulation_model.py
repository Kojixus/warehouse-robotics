from __future__ import annotations

import heapq
import random
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd


@dataclass
class GlobalParams:
    shift_minutes: int
    base_servers: int
    start_x: int
    start_y: int

    pick_seconds_per_line: float
    travel_seconds_per_unit: float

    base_congestion_mean_min: float
    base_congestion_sigma_min: float

    base_fault_prob_per_order: float
    fault_delay_min_min: float
    fault_delay_max_min: float
    capacity_penalty_scale_min: float
    congestion_gain: float
    fault_prob_gain: float


@dataclass
class ScenarioParams:
    name: str
    demand_multiplier: float
    robots_available_pct: float
    fault_multiplier: float
    queue_delay_multiplier: float


@dataclass
class RobotMinuteSignals:
    downtime_pct: np.ndarray
    congestion_pct: np.ndarray
    fault_pct: np.ndarray


def _manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _nearest_neighbor_route_distance(points: Iterable[Tuple[int, int]], start: Tuple[int, int]) -> int:
    remaining = list(points)
    if not remaining:
        return 0

    cur = start
    dist = 0
    while remaining:
        best_i = 0
        best_d = _manhattan(cur, remaining[0])
        for i in range(1, len(remaining)):
            d = _manhattan(cur, remaining[i])
            if d < best_d:
                best_d = d
                best_i = i
        nxt = remaining.pop(best_i)
        dist += best_d
        cur = nxt
    dist += _manhattan(cur, start)
    return dist


def build_location_map(locations: pd.DataFrame) -> Dict[str, Tuple[int, int]]:
    required = {"location_id", "x", "y"}
    missing = required - set(locations.columns)
    if missing:
        raise ValueError(f"Locations data missing columns: {sorted(missing)}")

    df = locations.loc[:, ["location_id", "x", "y"]].copy()
    df["location_id"] = df["location_id"].astype(str).str.strip()
    df["x"] = pd.to_numeric(df["x"], errors="coerce").fillna(0).astype(int)
    df["y"] = pd.to_numeric(df["y"], errors="coerce").fillna(0).astype(int)
    return dict(zip(df["location_id"], zip(df["x"], df["y"])))


def aggregate_orders(orders: pd.DataFrame, loc_map: Dict[str, Tuple[int, int]]) -> pd.DataFrame:
    required = {"order_id", "sku", "pick_location_id"}
    missing = required - set(orders.columns)
    if missing:
        raise ValueError(f"Orders data missing columns: {sorted(missing)}")

    df = orders.copy()
    df["order_id"] = df["order_id"].astype(str).str.strip()
    df["sku"] = df["sku"].astype(str).str.strip()
    df["pick_location_id"] = df["pick_location_id"].astype(str).str.strip()

    for c in ["order_time", "due_time", "priority", "qty"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
        else:
            df[c] = 0

    grp = df.groupby("order_id", as_index=False, sort=False).agg(
        order_time=("order_time", "min"),
        due_time=("due_time", "min"),
        priority=("priority", "min"),
        n_lines=("sku", "count"),
        total_qty=("qty", "sum"),
    )

    locs = (
        df.groupby("order_id", sort=False)["pick_location_id"]
        .agg(lambda s: tuple(pd.unique(s)))
        .reset_index(name="pick_locations")
    )
    out = grp.merge(locs, on="order_id", how="left", sort=False)
    out["route_points"] = out["pick_locations"].map(
        lambda lids: tuple(loc_map[lid] for lid in (lids or ()) if lid in loc_map)
    )
    return out


def apply_demand_multiplier(order_table: pd.DataFrame, shift_minutes: int, demand_multiplier: float, rng: random.Random) -> pd.DataFrame:
    base = order_table.copy()
    n = len(base)
    if n == 0:
        return base

    multiplier = float(demand_multiplier)
    if multiplier <= 0.0:
        return base.iloc[0:0].copy()

    target = max(1, int(round(n * multiplier)))
    if target == n:
        return base.reset_index(drop=True)

    sample_seed = rng.randint(0, 2**31 - 1)
    if target < n:
        return base.sample(n=target, replace=False, random_state=sample_seed).reset_index(drop=True)

    extra = target - n
    sampled = base.sample(n=extra, replace=True, random_state=sample_seed).copy()

    jitter = np.fromiter((rng.randint(-5, 5) for _ in range(extra)), dtype=int, count=extra)
    sampled["order_time"] = (sampled["order_time"].astype(int).values + jitter).clip(0, shift_minutes - 1)
    sampled["due_time"] = (sampled["due_time"].astype(int).values + jitter).clip(0, shift_minutes)

    sampled["order_id"] = [
        f"{oid}_DUP{rng.randint(1000, 9999)}_{i}"
        for i, oid in enumerate(sampled["order_id"].astype(str).tolist())
    ]
    out = pd.concat([base, sampled], axis=0, ignore_index=True)
    return out


def build_robot_minute_signals(
    robot_logs: pd.DataFrame | None,
    shift_minutes: int,
    fallback_fleet_size: int,
) -> RobotMinuteSignals | None:
    if robot_logs is None or robot_logs.empty or shift_minutes <= 0:
        return None

    required = {"robot_id", "timestamp_min", "duration_min", "state"}
    missing = required - set(robot_logs.columns)
    if missing:
        raise ValueError(f"Robot logs missing columns: {sorted(missing)}")

    df = robot_logs.copy()
    df["robot_id"] = df["robot_id"].astype(str).str.strip()
    df["state"] = df["state"].astype(str).str.upper().replace({"CHARGING": "CHARGE"})
    df["timestamp_min"] = pd.to_numeric(df["timestamp_min"], errors="coerce").fillna(0).astype(int)
    df["duration_min"] = pd.to_numeric(df["duration_min"], errors="coerce").fillna(0).clip(lower=0).astype(int)

    diff_charge = np.zeros(shift_minutes + 1, dtype=int)
    diff_fault = np.zeros(shift_minutes + 1, dtype=int)

    for row in df.itertuples(index=False):
        start = max(0, int(getattr(row, "timestamp_min")))
        dur = int(getattr(row, "duration_min"))
        if dur <= 0:
            continue
        end = min(shift_minutes, start + dur)
        if start >= shift_minutes or end <= start:
            continue

        state = str(getattr(row, "state"))
        if state == "CHARGE":
            diff_charge[start] += 1
            diff_charge[end] -= 1
        elif state == "FAULT":
            diff_fault[start] += 1
            diff_fault[end] -= 1

    charge_active = np.cumsum(diff_charge[:-1]).astype(float)
    fault_active = np.cumsum(diff_fault[:-1]).astype(float)

    fleet_size = max(int(fallback_fleet_size), int(df["robot_id"].nunique()), 1)
    congestion_pct = np.clip((charge_active + fault_active) / float(fleet_size), 0.0, 1.0)
    fault_pct = np.clip(fault_active / float(fleet_size), 0.0, 1.0)
    downtime_pct = np.clip(congestion_pct, 0.0, 1.0)

    return RobotMinuteSignals(
        downtime_pct=downtime_pct,
        congestion_pct=congestion_pct,
        fault_pct=fault_pct,
    )


def _add_base_service_time(order_table: pd.DataFrame, g: GlobalParams, start: Tuple[int, int]) -> pd.DataFrame:
    out = order_table.copy()
    route_cache: Dict[Tuple[Tuple[int, int], ...], int] = {}

    def route_distance(points: object) -> int:
        if isinstance(points, tuple):
            key = points
        elif isinstance(points, list):
            key = tuple(points)
        else:
            key = tuple()
        if key not in route_cache:
            route_cache[key] = _nearest_neighbor_route_distance(key, start=start)
        return route_cache[key]

    out["route_distance_units"] = out["route_points"].map(route_distance).astype(float)
    out["base_service_min"] = (
        (
            out["route_distance_units"] * float(g.travel_seconds_per_unit)
            + out["n_lines"].astype(float) * float(g.pick_seconds_per_line)
        )
        / 60.0
    )
    return out


def simulate_one_run(
    order_table: pd.DataFrame,
    g: GlobalParams,
    s: ScenarioParams,
    seed: int,
    robot_signals: RobotMinuteSignals | None = None,
) -> pd.DataFrame:
    n_orders = int(order_table.shape[0])
    if n_orders == 0:
        return pd.DataFrame()

    rng = np.random.default_rng(seed)
    servers = max(1, int(round(g.base_servers * float(s.robots_available_pct))))
    server_heap = [(0.0, i) for i in range(servers)]
    heapq.heapify(server_heap)

    p_fault = min(0.50, float(g.base_fault_prob_per_order) * float(s.fault_multiplier))
    arrivals = order_table["order_time"].to_numpy(dtype=float, copy=False)
    dues = order_table["due_time"].to_numpy(dtype=float, copy=False)
    base_service = order_table["base_service_min"].to_numpy(dtype=float, copy=False)
    order_ids = order_table["order_id"].astype(str).to_numpy()
    arrival_idx = arrivals.astype(int).clip(0, max(0, int(g.shift_minutes) - 1))

    if robot_signals is None:
        downtime_pct = np.zeros(n_orders, dtype=float)
        congestion_pressure = np.zeros(n_orders, dtype=float)
        fault_pressure = np.zeros(n_orders, dtype=float)
    else:
        downtime_pct = robot_signals.downtime_pct[arrival_idx]
        congestion_pressure = robot_signals.congestion_pct[arrival_idx]
        fault_pressure = robot_signals.fault_pct[arrival_idx]

    congestion = rng.normal(
        loc=float(g.base_congestion_mean_min),
        scale=float(g.base_congestion_sigma_min),
        size=n_orders,
    )
    np.maximum(congestion, 0.0, out=congestion)
    congestion *= float(s.queue_delay_multiplier)
    congestion *= 1.0 + float(g.congestion_gain) * congestion_pressure

    capacity_penalty = float(g.capacity_penalty_scale_min) * downtime_pct

    fault_prob = p_fault + float(g.fault_prob_gain) * fault_pressure
    np.clip(fault_prob, 0.0, 0.95, out=fault_prob)

    fault_delay = np.zeros(n_orders, dtype=float)
    if fault_prob.size > 0 and float(fault_prob.max()) > 0.0:
        fault_flags = rng.random(n_orders) < fault_prob
        n_faults = int(fault_flags.sum())
        if n_faults > 0:
            fault_delay[fault_flags] = rng.uniform(
                float(g.fault_delay_min_min),
                float(g.fault_delay_max_min),
                size=n_faults,
            )

    start_service = np.empty(n_orders, dtype=float)
    completion = np.empty(n_orders, dtype=float)
    wait = np.empty(n_orders, dtype=float)
    cycle_time = np.empty(n_orders, dtype=float)
    on_time = np.empty(n_orders, dtype=np.int8)

    for i in range(n_orders):
        arrival = arrivals[i]
        due = dues[i]

        free_time, server_id = heapq.heappop(server_heap)
        ss = arrival if arrival > free_time else free_time
        comp = ss + base_service[i] + congestion[i] + capacity_penalty[i] + fault_delay[i]

        heapq.heappush(server_heap, (comp, server_id))

        start_service[i] = ss
        completion[i] = comp
        wait[i] = ss - arrival
        cycle_time[i] = comp - arrival
        on_time[i] = 1 if comp <= due else 0

    return pd.DataFrame(
        {
            "order_id": order_ids,
            "arrival_min": arrivals,
            "due_min": dues,
            "start_service_min": start_service,
            "completion_min": completion,
            "wait_min": wait,
            "cycle_time_min": cycle_time,
            "on_time": on_time,
            "service_min_base": base_service,
            "congestion_min": congestion,
            "capacity_penalty_min": capacity_penalty,
            "fault_delay_min": fault_delay,
        }
    )


def run_scenario_monte_carlo(
    orders: pd.DataFrame,
    locations: pd.DataFrame,
    g: GlobalParams,
    s: ScenarioParams,
    runs: int,
    base_seed: int,
    robot_logs: pd.DataFrame | None = None,
) -> pd.DataFrame:
    loc_map = build_location_map(locations)
    order_table = aggregate_orders(orders, loc_map)
    start = (int(g.start_x), int(g.start_y))
    order_table = _add_base_service_time(order_table, g, start=start)
    robot_signals = build_robot_minute_signals(
        robot_logs=robot_logs,
        shift_minutes=int(g.shift_minutes),
        fallback_fleet_size=int(g.base_servers),
    )

    rng = random.Random(base_seed + 1337)
    order_table = apply_demand_multiplier(order_table, g.shift_minutes, float(s.demand_multiplier), rng)
    order_table = order_table.sort_values(
        ["order_time", "priority", "order_id"], ascending=[True, True, True]
    ).reset_index(drop=True)

    all_runs = []
    for r in range(int(runs)):
        seed = base_seed + r
        per_order = simulate_one_run(order_table, g, s, seed=seed, robot_signals=robot_signals)
        per_order["scenario"] = s.name
        per_order["run_index"] = r
        per_order["seed"] = seed
        all_runs.append(per_order)

    if not all_runs:
        return pd.DataFrame()
    return pd.concat(all_runs, axis=0).reset_index(drop=True)
