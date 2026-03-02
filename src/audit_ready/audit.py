import hashlib
import json
import os
import random
import platform
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

EST_TZ = timezone(timedelta(hours=-5), name='EST')

# Cycle count

CYCLE_COUNT_COLUMNS = [
    'count_id',
    'sku',
    'location_id',
    'abc_class',
    'expected_qty',
    'counted_qty',
    'variance_qty',
    'variance_pct',
    'reason_code',
    'counted_by',
    'count_time_min',
]

EXCEPTION_COLUMNS = [
    'ex_ID',
    'order_id',
    'sku',
    'location_id',
    'ex_type',
    'severity',
    'time_created',
    'time_resolved',
    'time_resolution',
    'status',
    'role',
    'notes',
    'sla_target_min',
    'within_sla',
]


def cycle(
    inventory: pd.DataFrame,
    seed: int = 42,
    top_n_a: int = 30,
    random_n: int = 20,
) -> pd.DataFrame:
    if inventory is None or inventory.empty:
        return pd.DataFrame(columns=CYCLE_COUNT_COLUMNS)

    rng = random.Random(seed)

    inv = inventory.copy()
    inv['speed_per_day'] = pd.to_numeric(inv['speed_per_day'], errors='coerce').fillna(
        0.0
    )
    inv['qty_on_hand'] = (
        pd.to_numeric(inv['qty_on_hand'], errors='coerce').fillna(0).astype(int)
    )

    items = (
        inv[inv['abc_class'] == 'A']
        .sort_values('speed_per_day', ascending=False)
        .head(top_n_a)
    )
    remainder = inv.drop(items.index)
    if not remainder.empty:
        rand_sample = remainder.sample(
            n=min(random_n, len(remainder)), random_state=seed
        )
    else:
        rand_sample = remainder
    plan = pd.concat([items, rand_sample], axis=0).reset_index(drop=True)
    if plan.empty:
        return pd.DataFrame(columns=CYCLE_COUNT_COLUMNS)

    rows = []
    for idx, row in enumerate(plan.itertuples(index=False), start=1):
        expected = int(row.qty_on_hand)  # type: ignore[arg-type]
        abc = str(row.abc_class)
        # probability: C > B > A
        p_var = 0.02 if abc == 'A' else (0.05 if abc == 'B' else 0.12)
        prop_variance = 0
        reason = ''
        if rng.random() < p_var:
            if rng.random() < 0.75:
                shrink_cap = max(1, min(6, expected if expected > 0 else 3))
                prop_variance = -rng.randint(1, shrink_cap)
                reason = 'SHRINK'
            else:
                prop_variance = rng.randint(1, 5)
                reason = 'OVER'
        counted = max(0, expected + prop_variance)
        act_variance = counted - expected
        if act_variance == 0:
            reason = ''
        if expected > 0:
            var_pct = round((act_variance / expected) * 100.0, 2)
        else:
            var_pct = 0.0
        rows.append(
            {
                'count_id': f'CC{str(idx).zfill(4)}',
                'sku': str(row.sku),
                'location_id': str(row.location_id),
                'abc_class': abc,
                'expected_qty': expected,
                'counted_qty': counted,
                'variance_qty': act_variance,
                'variance_pct': var_pct,
                'reason_code': reason,
                'counted_by': rng.choice(['team']),
                'count_time_min': rng.randint(30, 420),
            }
        )
    return pd.DataFrame.from_records(rows, columns=CYCLE_COUNT_COLUMNS)


def generate_cycle_counts(
    inventory_snapshot: pd.DataFrame,
    seed: int = 42,
    top_n_a: int = 30,
    random_n: int = 20,
) -> pd.DataFrame:
    return cycle(
        inventory_snapshot,
        seed=seed,
        top_n_a=top_n_a,
        random_n=random_n,
    )


# Summarize cycle count results
def sum_cycle_counts(cycle_counts: pd.DataFrame) -> pd.DataFrame:
    if cycle_counts is None or cycle_counts.empty:
        return pd.DataFrame(
            [
                {
                    'total_cycles': 0,
                    'variance_lines': 0,
                    'avg_variance_pct': 0.0,
                    'net_variance_units': 0,
                    'absolute_variance_units': 0,
                }
            ]
        )
    df = cycle_counts.copy()
    df['variance_qty'] = (
        pd.to_numeric(df['variance_qty'], errors='coerce').fillna(0).astype(int)
    )
    df = df[df['variance_qty'] != 0]
    counted = int(df.shape[0])
    with_var = int(df['variance_qty'].ne(0).sum())
    accuracy = (
        round(((counted - with_var) / counted) * 100.0, 2) if counted > 0 else 0.0
    )
    net_unts = int(df['variance_qty'].sum())
    abs_units = int(df['variance_qty'].abs().sum())
    return pd.DataFrame(
        [
            {
                'total_cycles': counted,
                'variance_lines': with_var,
                'line_accuracy_pct': accuracy,
                'net_variance_units': net_unts,
                'absolute_variance_units': abs_units,
            }
        ]
    )


def summarize_cycle_counts(cycle_counts: pd.DataFrame) -> pd.DataFrame:
    return sum_cycle_counts(cycle_counts)


# Inventory


def require_columns(df: pd.DataFrame, required: list[str], frame_name: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f'{frame_name} missing required columns: {missing}')


def build_abc_classes(skus: pd.DataFrame) -> pd.DataFrame:
    require_columns(skus, ['sku', 'speed_per_day'], 'skus')

    df = skus[['sku', 'speed_per_day']].copy()
    df['sku'] = df['sku'].astype(str)
    df['speed_per_day'] = pd.to_numeric(df['speed_per_day'], errors='coerce').fillna(
        0.0
    )  # noqa
    df = df.sort_values('speed_per_day', ascending=False).reset_index(drop=True)
    total = float(df['speed_per_day'].sum())
    df['cumsum_speed'] = df['speed_per_day'].cumsum()
    if total > 0:
        df['cum_pct'] = df['cumsum_speed'] / total
    else:
        df['cum_pct'] = 0.0

    def cls(pct: float) -> str:
        if pct <= 0.80:
            return 'A'
        if pct <= 0.95:
            return 'B'
        return 'C'

    df['abc_class'] = df['cum_pct'].apply(cls)
    cols = ['sku', 'speed_per_day', 'abc_class']
    df['sort_abc'] = pd.Categorical(
        df['abc_class'], categories=['A', 'B', 'C'], ordered=True
    )
    return (
        df[cols + ['sort_abc']]
        .sort_values(
            ['sort_abc', 'speed_per_day'],
            ascending=[True, False],
            na_position='last',
        )
        .drop(columns=['sort_abc'])
        .reset_index(drop=True)
    )


def sku_locations(orders: pd.DataFrame, locations: pd.DataFrame) -> pd.DataFrame:
    require_columns(orders, ['sku', 'pick_location_id'], 'orders')
    require_columns(locations, ['location_id'], 'locations')
    clean = orders[['sku', 'pick_location_id']].dropna().copy()
    if clean.empty:
        return pd.DataFrame(columns=['sku', 'location_id'])
    clean['sku'] = clean['sku'].astype(str)
    clean['pick_location_id'] = clean['pick_location_id'].astype(str)
    mode_loc = (
        clean.groupby(['sku', 'pick_location_id'], as_index=False)
        .size()
        .sort_values(
            ['sku', 'size', 'pick_location_id'],
            ascending=[True, False, True],
        )
    )
    out = mode_loc[['sku', 'pick_location_id']].rename(
        columns={'pick_location_id': 'location_id'}
    )
    return out.sort_values(['sku', 'location_id']).reset_index(drop=True)


def slotting(sku_home: pd.DataFrame, move_list_path: str) -> pd.DataFrame:
    if not os.path.exists(move_list_path):
        return sku_home
    moves = pd.read_csv(move_list_path)
    if (
        moves.empty
        or 'sku' not in moves.columns
        or 'to_location_id' not in moves.columns
    ):
        return sku_home
    mapping = (
        moves[['sku', 'to_location_id']]
        .dropna()
        .astype(str)
        .drop_duplicates(subset=['sku'], keep='last')
        .set_index('sku')['to_location_id']
    )
    out = sku_home.copy()
    out['sku'] = out['sku'].astype(str)
    out['location_id'] = out['location_id'].astype(str)
    out['location_id'] = out['sku'].map(mapping).fillna(out['location_id']).astype(str)
    return out


def inventory_report(
    skus: pd.DataFrame,
    sku_abc: pd.DataFrame,
    sku_locations: pd.DataFrame,
    orders: pd.DataFrame,
    seed: int = 42,
) -> pd.DataFrame:
    require_columns(skus, ['sku', 'speed_per_day'], 'skus')
    require_columns(sku_abc, ['sku', 'abc_class'], 'sku_abc')
    require_columns(sku_locations, ['sku', 'location_id'], 'sku_locations')
    require_columns(orders, ['sku', 'pick_location_id'], 'orders')
    rng = random.Random(seed)

    # Start from SKU master.
    df = skus.copy()
    df['sku'] = df['sku'].astype(str)
    df['speed_per_day'] = pd.to_numeric(df['speed_per_day'], errors='coerce').fillna(
        0.0
    )

    # Join ABC by sku only to avoid float-join mismatches.
    abc = sku_abc[['sku', 'abc_class']].copy()
    abc['sku'] = abc['sku'].astype(str)
    abc = abc.drop_duplicates(subset=['sku'], keep='first')
    df = df.merge(abc, on='sku', how='left')

    # Join home locations.
    locs = sku_locations[['sku', 'location_id']].copy()
    locs['sku'] = locs['sku'].astype(str)
    locs['location_id'] = locs['location_id'].astype(str)
    locs = locs.drop_duplicates(subset=['sku'], keep='first')
    df = df.merge(locs, on='sku', how='left')

    # Build pool of possible locations from orders and existing assignments.
    order_loc = orders['pick_location_id'].dropna().astype(str)
    known_loc = (
        locs['location_id'].dropna().astype(str)
        if not locs.empty
        else pd.Series(dtype=str)
    )
    loc_pool = pd.concat([order_loc, known_loc], ignore_index=True)
    loc_pool = [x for x in loc_pool.tolist() if x]
    if not loc_pool:
        loc_pool = ['UNASSIGNED']

    # Assign missing locations.
    df['location_id'] = df['location_id'].fillna('').astype(str)
    missing_loc = df['location_id'].eq('')
    if missing_loc.any():
        df.loc[missing_loc, 'location_id'] = [
            rng.choice(loc_pool) for _ in range(int(missing_loc.sum()))
        ]

    # Reserved qty from open orders demand (sum qty by SKU).
    ord_df = orders.copy()
    ord_df['sku'] = ord_df['sku'].astype(str)
    if 'qty' in ord_df.columns:
        ord_df['qty'] = pd.to_numeric(ord_df['qty'], errors='coerce').fillna(1)
        reserved = ord_df.groupby('sku', as_index=False).agg(
            reserved_qty=('qty', 'sum')
        )
    else:
        reserved = ord_df.groupby('sku', as_index=False).agg(
            reserved_qty=('sku', 'size')
        )
    df = df.merge(reserved, on='sku', how='left').fillna({'reserved_qty': 0})
    df['reserved_qty'] = (
        pd.to_numeric(df['reserved_qty'], errors='coerce').fillna(0).astype(int)
    )

    # On-hand qty: days-of-cover * speed, adjusted by ABC.
    abc_values = df['abc_class'].fillna('C').astype(str).tolist()
    covers = []
    for abc_class in abc_values:
        if abc_class == 'A':
            covers.append(rng.randint(7, 14))
        elif abc_class == 'B':
            covers.append(rng.randint(5, 10))
        else:
            covers.append(rng.randint(3, 8))
    base_on_hand = (df['speed_per_day'] * pd.Series(covers)).round().astype(int)

    noise = pd.Series([rng.randint(-3, 8) for _ in range(len(df))])
    df['qty_on_hand'] = (base_on_hand + noise).clip(lower=0).astype(int)

    # Available.
    df['available_qty'] = (
        (df['qty_on_hand'] - df['reserved_qty']).clip(lower=0).astype(int)
    )

    # Unit cost (for value impact).
    if 'unit_cost' in df.columns:
        df['unit_cost'] = pd.to_numeric(df['unit_cost'], errors='coerce').fillna(0.0)
    else:
        df['unit_cost'] = [round(rng.uniform(8.0, 220.0), 2) for _ in range(len(df))]

    # Reorder logic.
    lead_time_days = pd.Series([rng.randint(3, 7) for _ in range(len(df))])
    safety_stock = pd.Series([rng.randint(5, 40) for _ in range(len(df))])
    df['reorder'] = (
        (df['speed_per_day'] * lead_time_days + safety_stock).round().astype(int)
    )
    target_days = pd.Series([rng.randint(10, 18) for _ in range(len(df))])
    target_stock = (df['speed_per_day'] * target_days).round().astype(int)
    df['reorder_qty'] = (
        (df['reorder'] + target_stock - df['qty_on_hand']).clip(lower=0).astype(int)
    )

    snapshot_est = datetime.now(EST_TZ).strftime('%Y-%m-%dT%H:%M:%S EST')
    df['snapshot_est'] = snapshot_est

    cols = [
        'snapshot_est',
        'sku',
        'abc_class',
        'location_id',
        'speed_per_day',
        'qty_on_hand',
        'reserved_qty',
        'available_qty',
        'unit_cost',
        'reorder',
        'reorder_qty',
    ]

    df['sort_abc'] = pd.Categorical(
        df['abc_class'], categories=['A', 'B', 'C'], ordered=True
    )
    return (
        df[cols + ['sort_abc']]
        .sort_values(
            ['sort_abc', 'speed_per_day'],
            ascending=[True, False],
            na_position='last',
        )
        .drop(columns=['sort_abc'])
        .reset_index(drop=True)
    )


def infer_sku_home_locations(
    orders: pd.DataFrame, locations: pd.DataFrame
) -> pd.DataFrame:
    return sku_locations(orders, locations)


def apply_slotting_moves_if_present(
    sku_home: pd.DataFrame, move_list_path: str
) -> pd.DataFrame:
    return slotting(sku_home, move_list_path)


def generate_inventory_snapshot(
    skus: pd.DataFrame,
    sku_abc: pd.DataFrame,
    sku_home_locations: pd.DataFrame,
    orders: pd.DataFrame,
    seed: int = 42,
) -> pd.DataFrame:
    return inventory_report(
        skus=skus,
        sku_abc=sku_abc,
        sku_locations=sku_home_locations,
        orders=orders,
        seed=seed,
    )


# Robot


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def robot_falut(robot_logs: pd.DataFrame | None) -> set[int]:
    '''
    Returns a set of high fault-pressure minutes (>=2 robots in FAULT).
    '''
    if robot_logs is None or robot_logs.empty:
        return set()
    required = {'state', 'timestamp_min', 'duration_min'}
    if not required.issubset(set(robot_logs.columns)):
        return set()
    shift_minutes = 480
    diff = [0] * (shift_minutes + 1)
    fault_rows = robot_logs[robot_logs['state'].astype(str).str.upper() == 'FAULT']
    for row in fault_rows.itertuples(index=False):
        start = max(0, to_int(getattr(row, 'timestamp_min', 0), 0))
        dur = max(0, to_int(getattr(row, 'duration_min', 0), 0))
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


def exceptions(
    orders: pd.DataFrame,
    inventory: pd.DataFrame,
    robot_logs: pd.DataFrame | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    '''
    Creates a realistic exceptions log:
      - SHORT_PICK (inventory available < ordered qty)
      - DAMAGED
      - LOCATION_BLOCKED
      - ROBOT_DELAY (if order_time occurs during fault pressure window)
    '''
    if orders is None or orders.empty:
        return pd.DataFrame(columns=EXCEPTION_COLUMNS)
    rng = random.Random(seed)

    inv = inventory[['sku', 'available_qty']].copy()
    inv['sku'] = inv['sku'].astype(str)
    inv['available_qty'] = (
        pd.to_numeric(inv['available_qty'], errors='coerce').fillna(0).astype(int)
    )
    inv_map = dict(zip(inv['sku'], inv['available_qty']))

    fault_minutes = robot_falut(robot_logs)

    rows = []
    exc_i = 0
    # Base probabilities (tune for realism; not too noisy)
    p_damaged = 0.008
    p_loc_blocked = 0.006

    for order in orders.itertuples(index=False):
        order_id = str(getattr(order, 'order_id', ''))
        sku = str(getattr(order, 'sku', ''))
        loc = str(getattr(order, 'pick_location_id', ''))
        qty = max(1, to_int(getattr(order, 'qty', 1), 1))
        order_time = to_int(
            getattr(order, 'order_time', rng.randint(0, 470)),
            rng.randint(0, 470),
        )
        order_time = min(479, max(0, order_time))

        # ROBOT_DELAY
        if order_time in fault_minutes and rng.random() < 0.20:
            exc_i += 1
            created = order_time
            sla = 45
            resolved = min(479, created + rng.randint(10, 80))
            rows.append(
                {
                    'ex_ID': f'EXC{str(exc_i).zfill(5)}',
                    'order_id': order_id,
                    'sku': sku,
                    'location_id': loc,
                    'ex_type': 'ROBOT_DELAY',
                    'severity': 'WARN',
                    'time_created': created,
                    'time_resolved': resolved,
                    'sla_target_min': sla,
                    'status': 'CLOSED',
                    'role': 'ops_supervisor',
                    'notes': (
                        'Order delayed due to elevated robot fault pressure '
                        'window.'
                    ),
                }
            )
        avail = int(inv_map.get(sku, 0))
        if avail < qty and rng.random() < 0.85:
            exc_i += 1
            created = min(479, max(0, order_time + rng.randint(0, 25)))
            sla = 120
            resolved = min(479, created + rng.randint(20, 180))
            rows.append(
                {
                    'ex_ID': f'EXC{str(exc_i).zfill(5)}',
                    'order_id': order_id,
                    'sku': sku,
                    'location_id': loc,
                    'ex_type': 'SHORT_PICK',
                    'severity': 'CRIT',
                    'time_created': created,
                    'time_resolved': resolved,
                    'sla_target_min': sla,
                    'status': 'CLOSED',
                    'role': 'inventory_control',
                    'notes': (
                        'Pick short due to insufficient available inventory; '
                        'requires investigation/adjustment.'
                    ),
                }
            )
            continue

        # successful picks simulation from inventory
        inv_map[sku] = max(0, avail - qty)

        # DAMAGED
        if rng.random() < p_damaged:
            exc_i += 1
            created = min(479, max(0, order_time + rng.randint(0, 30)))
            sla = 90
            resolved = min(479, created + rng.randint(10, 140))
            rows.append(
                {
                    'ex_ID': f'EXC{str(exc_i).zfill(5)}',
                    'order_id': order_id,
                    'sku': sku,
                    'location_id': loc,
                    'ex_type': 'DAMAGED',
                    'severity': 'WARN',
                    'time_created': created,
                    'time_resolved': resolved,
                    'sla_target_min': sla,
                    'status': 'CLOSED',
                    'role': 'qa',
                    'notes': 'Unit damaged; re-pick or replace required.',
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
                    'ex_ID': f'EXC{str(exc_i).zfill(5)}',
                    'order_id': order_id,
                    'sku': sku,
                    'location_id': loc,
                    'ex_type': 'LOCATION_BLOCKED',
                    'severity': 'WARN',
                    'time_created': created,
                    'time_resolved': resolved,
                    'sla_target_min': sla,
                    'status': 'CLOSED',
                    'role': 'floor_lead',
                    'notes': (
                        'Location temporarily inaccessible '
                        '(congestion/obstruction); reroute or clear.'
                    ),
                }
            )

    out = pd.DataFrame.from_records(rows)
    if out.empty:
        return pd.DataFrame(columns=EXCEPTION_COLUMNS)

    out['time_created'] = (
        pd.to_numeric(out['time_created'], errors='coerce').fillna(0).astype(int)
    )
    out['time_resolved'] = (
        pd.to_numeric(out['time_resolved'], errors='coerce').fillna(0).astype(int)
    )
    out['sla_target_min'] = (
        pd.to_numeric(out['sla_target_min'], errors='coerce').fillna(0).astype(int)
    )

    out['time_resolution'] = (out['time_resolved'] - out['time_created']).clip(lower=0)
    out['within_sla'] = out['time_resolution'] <= out['sla_target_min']

    out = out.sort_values(
        ['time_created', 'severity'], ascending=[True, False]
    ).reset_index(drop=True)
    return out.reindex(columns=EXCEPTION_COLUMNS)


def summarize_exception_sla(exceptions: pd.DataFrame) -> pd.DataFrame:
    if exceptions is None or exceptions.empty:
        return pd.DataFrame(
            columns=[
                'ex_type',
                'count',
                'pct_within_sla',
                'avg_resolution_min',
                'sla_breaches',
            ]
        )
    df = exceptions.copy()
    if 'time_resolution' not in df.columns:
        df['time_created'] = (
            pd.to_numeric(df['time_created'], errors='coerce').fillna(0).astype(int)
        )
        df['time_resolved'] = (
            pd.to_numeric(df['time_resolved'], errors='coerce').fillna(0).astype(int)
        )
        df['time_resolution'] = (df['time_resolved'] - df['time_created']).clip(
            lower=0
        )
    if 'within_sla' not in df.columns:
        df['sla_target_min'] = (
            pd.to_numeric(df['sla_target_min'], errors='coerce').fillna(0).astype(int)
        )
        df['within_sla'] = df['time_resolution'] <= df['sla_target_min']
    df['within_sla'] = df['within_sla'].astype(bool)
    summary = (
        df.groupby('ex_type', dropna=False)
        .agg(
            count=('ex_type', 'size'),
            within_sla_count=('within_sla', 'sum'),
            avg_resolution_min=('time_resolution', 'mean'),
        )
        .reset_index()
    )
    summary['pct_within_sla'] = (
        summary['within_sla_count'] / summary['count'] * 100.0
    ).round(2)
    summary['avg_resolution_min'] = summary['avg_resolution_min'].astype(float).round(
        2
    )
    summary['sla_breaches'] = (summary['count'] - summary['within_sla_count']).astype(
        int
    )
    return (
        summary[
            [
                'ex_type',
                'count',
                'pct_within_sla',
                'avg_resolution_min',
                'sla_breaches',
            ]
        ]
        .sort_values(
            ['sla_breaches', 'count'],
            ascending=[False, False],
        )
        .reset_index(drop=True)
    )


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as file_obj:
            for chunk in iter(lambda: file_obj.read(1024 * 1024), b''):
                h.update(chunk)
    except OSError:
        return ''
    return h.hexdigest()


def file_entry(path: str) -> dict:
    path_str = os.fspath(path)
    exists = os.path.exists(path_str)
    is_file = os.path.isfile(path_str) if exists else False
    size_bytes = 0
    sha256 = ''
    if is_file:
        try:
            size_bytes = os.path.getsize(path_str)
        except OSError:
            size_bytes = 0
        sha256 = sha256_file(path_str)
    return {
        'path': path_str,
        'exists': exists,
        'size_bytes': int(size_bytes),
        'sha256': sha256,
    }


def parent_dir(out_path: str) -> None:
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def run_manifest(
    out_path: str,
    run_id: str,
    seed: int,
    inputs: list,
    outputs: list,
    extra: dict,
) -> None:
    ts = datetime.now(EST_TZ).strftime('%Y-%m-%dT%H:%M:%S EST')

    manifest = {
        'run_id': run_id,
        'timestamp_est': ts,
        'seed': int(seed),
        'inputs': [file_entry(path) for path in inputs],
        'outputs': [file_entry(path) for path in outputs],
        'environment': extra or {},
    }

    parent_dir(out_path)
    with open(out_path, 'w', encoding='utf-8') as fp:
        json.dump(manifest, fp, indent=2, sort_keys=True)


def evidence_index(
    out_path: str,
    run_id: str,
    seed: int,
    input_files: list,
    key_outputs: dict,
) -> None:
    ts = datetime.now(EST_TZ).strftime('%Y-%m-%dT%H:%M:%S EST')

    lines = [
        '# Audit Evidence Index',
        '',
        f'- Run ID: **{run_id}**',
        f'- Timestamp (EST): **{ts}**',
        f'- Seed: **{seed}**',
        '',
        '## Inputs',
        '',
    ]

    for path in input_files:
        lines.append(f'- `{path}`')

    lines.extend(
        [
            '',
            '## Outputs (Evidence)',
            '',
        ]
    )

    for label, path in key_outputs.items():
        lines.append(f'- **{label}:** `{path}`')

    lines.extend(
        [
            '',
            '## What this pack demonstrates',
            '',
            (
                '- Inventory snapshot is reproducible and traceable to '
                'specific inputs (SKU master, locations, orders).'
            ),
            (
                '- Cycle counts quantify variance and provide an accuracy '
                'signal for inventory control.'
            ),
            (
                '- Exceptions log captures operational disruptions '
                'and enables SLA performance reporting.'
            ),
            (
                '- Run manifest provides file hashes for evidence integrity '
                'and repeatable verification.'
            ),
            '',
        ]
    )

    parent_dir(out_path)
    with open(out_path, 'w', encoding='utf-8') as fp:
        fp.write('\n'.join(lines))


def _ensure_parent_dir(out_path: str) -> None:
    parent_dir(out_path)


def write_run_manifest(
    out_path: str,
    run_id: str,
    seed: int,
    inputs: list,
    outputs: list,
    extra: dict,
) -> None:
    run_manifest(
        out_path=out_path,
        run_id=run_id,
        seed=seed,
        inputs=inputs,
        outputs=outputs,
        extra=extra,
    )


def write_evidence_index(
    out_path: str,
    run_id: str,
    seed: int,
    input_files: list,
    key_outputs: dict,
) -> None:
    evidence_index(
        out_path=out_path,
        run_id=run_id,
        seed=seed,
        input_files=input_files,
        key_outputs=key_outputs,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / 'data/simulated'
OUTPUT_REPORTS_DIR = PROJECT_ROOT / 'output/reports'
OUTPUT_AUDIT_DIR = PROJECT_ROOT / 'output/audit'
SLOTTING_MOVE_LIST_PATH = OUTPUT_REPORTS_DIR / 'move_list_top50.csv'
ROBOT_LOG_CANDIDATES: tuple[Path, ...] = (
    DATA_DIR / 'robot_logs.csv',
    Path('output/operations_data/simulated/robot_logs.csv'),
    Path('output/control_tower_data/simulated/robot_logs.csv'),
    Path('output/simulated/robot_logs.csv'),
)


def _load_csv_resilient(path: Path, required_columns: list[str]) -> pd.DataFrame:
    '''
    Read CSV files and repair malformed files where each full row is quoted.
    '''
    df = pd.read_csv(path)
    if set(required_columns).issubset(df.columns):
        return df

    if df.shape[1] == 1 and ',' in str(df.columns[0]):
        repaired_columns = [c.strip().strip('"') for c in str(df.columns[0]).split(',')]
        repaired = (
            df.iloc[:, 0]
            .astype(str)
            .str.strip()
            .str.strip('"')
            .str.split(',', expand=True)
        )
        if repaired.shape[1] == len(repaired_columns):
            repaired.columns = repaired_columns
            df = repaired

    for column_name in df.columns:
        if df[column_name].dtype == object:
            df[column_name] = df[column_name].astype(str).str.strip().str.strip('"')

    missing = [
        column_name for column_name in required_columns if column_name not in df.columns
    ]
    if missing:
        raise ValueError(f'{path.as_posix()} missing required columns: {missing}')
    return df


def ensure_dirs() -> None:
    for folder in (DATA_DIR, OUTPUT_REPORTS_DIR, OUTPUT_AUDIT_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def resolve_robot_logs_path() -> Path | None:
    for path in ROBOT_LOG_CANDIDATES:
        if path.exists():
            return path
    return None


def load_inputs() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame | None,
    Path | None,
]:
    skus = _load_csv_resilient(DATA_DIR / 'skus.csv', ['sku'])
    if 'speed_per_day' not in skus.columns and 'velocity_per_day' in skus.columns:
        skus = skus.rename(columns={'velocity_per_day': 'speed_per_day'})
    if 'speed_per_day' not in skus.columns:
        raise ValueError('skus missing required columns: [\'speed_per_day\']')
    locations = _load_csv_resilient(
        DATA_DIR / 'locations.csv',
        ['location_id'],
    )
    orders = _load_csv_resilient(
        DATA_DIR / 'orders.csv', ['order_id', 'sku', 'pick_location_id']
    )

    robot_logs_path = resolve_robot_logs_path()
    robot_logs = (
        _load_csv_resilient(
            robot_logs_path,
            ['state', 'timestamp_min', 'duration_min'],
        )
        if robot_logs_path
        else None
    )

    return skus, locations, orders, robot_logs, robot_logs_path


def main() -> None:
    ensure_dirs()

    # ---- Config ----
    seed = 42
    run_id_timestamp = datetime.now(EST_TZ).strftime('%Y%m%dT%H%M%S')
    run_id = f'run_{run_id_timestamp}EST_{uuid.uuid4().hex[:8]}'

    # ---- Load inputs ----
    skus, locations, orders, robot_logs, robot_logs_path = load_inputs()
    if robot_logs_path:
        print(f'Using robot logs: {robot_logs_path.as_posix()}')
    else:
        print('Using robot logs: none found (ROBOT_DELAY signal disabled)')

    # ---- Build ABC + home locations ----
    sku_abc = build_abc_classes(skus)
    sku_home = infer_sku_home_locations(orders, locations)
    sku_home = apply_slotting_moves_if_present(
        sku_home, SLOTTING_MOVE_LIST_PATH.as_posix()
    )

    # ---- Inventory snapshot ----
    inventory = generate_inventory_snapshot(
        skus=skus,
        sku_abc=sku_abc,
        sku_home_locations=sku_home,
        orders=orders,
        seed=seed,
    )
    inv_path = DATA_DIR / 'inventory_snapshot.csv'
    inventory.to_csv(inv_path, index=False)

    # Inventory accuracy report (high-level)
    inv_accuracy = pd.DataFrame(
        [
            {
                'snapshot_est': (
                    inventory['snapshot_est'].iloc[0] if not inventory.empty else ''
                ),
                'sku_count': (
                    int(inventory['sku'].nunique()) if not inventory.empty else 0
                ),
                'total_on_hand_units': (
                    int(inventory['qty_on_hand'].sum()) if not inventory.empty else 0
                ),
                'total_reserved_units': (
                    int(inventory['reserved_qty'].sum()) if not inventory.empty else 0
                ),
                'total_available_units': (
                    int(inventory['available_qty'].sum()) if not inventory.empty else 0
                ),
                'total_inventory_value_est': (
                    float((inventory['qty_on_hand'] * inventory['unit_cost']).sum())
                    if not inventory.empty
                    else 0.0
                ),
            }
        ]
    )
    inv_accuracy_path = OUTPUT_REPORTS_DIR / 'inventory_accuracy.csv'
    inv_accuracy.to_csv(inv_accuracy_path, index=False)

    # ---- Cycle counts ----
    cycle_counts = generate_cycle_counts(
        inventory_snapshot=inventory,
        seed=seed,
        top_n_a=30,
        random_n=20,
    )
    cycle_counts_path = DATA_DIR / 'cycle_counts.csv'
    cycle_counts.to_csv(cycle_counts_path, index=False)

    cycle_count_results = summarize_cycle_counts(cycle_counts)
    cycle_count_results_path = OUTPUT_REPORTS_DIR / 'cycle_count_results.csv'
    cycle_count_results.to_csv(cycle_count_results_path, index=False)

    # ---- Exceptions + SLA ----
    exceptions_log = exceptions(
        orders=orders,
        inventory=inventory,
        robot_logs=robot_logs,
        seed=seed,
    )
    exceptions_path = OUTPUT_REPORTS_DIR / 'exceptions.csv'
    exceptions_log.to_csv(exceptions_path, index=False)

    exception_sla = summarize_exception_sla(exceptions_log)
    exception_sla_path = OUTPUT_REPORTS_DIR / 'exception_resolution_sla.csv'
    exception_sla.to_csv(exception_sla_path, index=False)

    # ---- Audit evidence pack ----
    inputs = [
        DATA_DIR / 'locations.csv',
        DATA_DIR / 'skus.csv',
        DATA_DIR / 'orders.csv',
    ]
    if robot_logs is not None and robot_logs_path:
        inputs.append(robot_logs_path)
    if SLOTTING_MOVE_LIST_PATH.exists():
        inputs.append(SLOTTING_MOVE_LIST_PATH)

    run_manifest_path = OUTPUT_AUDIT_DIR / 'run_manifest.json'
    evidence_index_path = OUTPUT_AUDIT_DIR / 'evidence_index.md'

    outputs = [
        inv_path,
        cycle_counts_path,
        inv_accuracy_path,
        cycle_count_results_path,
        exceptions_path,
        exception_sla_path,
        run_manifest_path,
        evidence_index_path,
    ]

    write_run_manifest(
        out_path=run_manifest_path.as_posix(),
        run_id=run_id,
        seed=seed,
        inputs=[path.as_posix() for path in inputs],
        outputs=[path.as_posix() for path in outputs if path.suffix.lower() == '.csv'],
        extra={
            'python_version': platform.python_version(),
            'platform': platform.platform(),
        },
    )

    write_evidence_index(
        out_path=evidence_index_path.as_posix(),
        run_id=run_id,
        seed=seed,
        input_files=[path.as_posix() for path in inputs],
        key_outputs={
            'Inventory snapshot': inv_path.as_posix(),
            'Cycle counts': cycle_counts_path.as_posix(),
            'Inventory summary': inv_accuracy_path.as_posix(),
            'Cycle count results': cycle_count_results_path.as_posix(),
            'Exceptions log': exceptions_path.as_posix(),
            'SLA summary': exception_sla_path.as_posix(),
            'Run manifest': run_manifest_path.as_posix(),
        },
    )

    print('DONE: Week 5 generated:')
    for path in outputs:
        if path.exists():
            print(f' - {path.as_posix()}')
        else:
            print(f' - (missing) {path.as_posix()}')


if __name__ == '__main__':
    main()
