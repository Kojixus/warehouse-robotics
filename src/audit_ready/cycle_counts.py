import random

import pandas as pd


CYCLE_COUNT_COLUMNS = [
    "count_id",
    "sku",
    "location_id",
    "abc_class",
    "expected_qty",
    "counted_qty",
    "variance_qty",
    "variance_pct",
    "reason_code",
    "counted_by",
    "count_time_min",
]


def generate_cycle_counts(
    inventory_snapshot: pd.DataFrame,
    seed: int = 42,
    top_n_a: int = 30,
    random_n: int = 20,
) -> pd.DataFrame:
    if inventory_snapshot is None or inventory_snapshot.empty:
        return pd.DataFrame(columns=CYCLE_COUNT_COLUMNS)

    rng = random.Random(seed)

    inv = inventory_snapshot.copy()
    inv["velocity_per_day"] = pd.to_numeric(
        inv["velocity_per_day"], errors="coerce"
    ).fillna(0.0)
    inv["on_hand_qty"] = (
        pd.to_numeric(inv["on_hand_qty"], errors="coerce").fillna(0).astype(int)
    )

    a_items = (
        inv[inv["abc_class"] == "A"]
        .sort_values("velocity_per_day", ascending=False)
        .head(top_n_a)
    )
    remainder = inv.drop(a_items.index)

    if not remainder.empty:
        rand_sample = remainder.sample(
            n=min(random_n, len(remainder)), random_state=seed
        )
    else:
        rand_sample = remainder

    plan = pd.concat([a_items, rand_sample], axis=0).reset_index(drop=True)
    if plan.empty:
        return pd.DataFrame(columns=CYCLE_COUNT_COLUMNS)

    rows = []
    for idx, row in enumerate(plan.itertuples(index=False), start=1):
        expected = int(row.on_hand_qty)
        abc = str(row.abc_class)

        # Variance probability: C > B > A
        p_var = 0.05 if abc == "A" else (0.08 if abc == "B" else 0.12)

        proposed_variance = 0
        reason = ""
        if rng.random() < p_var:
            # Mostly shrink, sometimes overage.
            if rng.random() < 0.75:
                shrink_cap = max(1, min(6, expected if expected > 0 else 3))
                proposed_variance = -rng.randint(1, shrink_cap)
                reason = "SHRINK"
            else:
                proposed_variance = rng.randint(1, 5)
                reason = "OVER"

        counted = max(0, expected + proposed_variance)
        actual_variance = counted - expected
        if actual_variance == 0:
            reason = ""

        if expected > 0:
            var_pct = round((actual_variance / expected) * 100.0, 2)
        else:
            var_pct = 0.0

        rows.append(
            {
                "count_id": f"CC{str(idx).zfill(4)}",
                "sku": str(row.sku),
                "location_id": str(row.location_id),
                "abc_class": abc,
                "expected_qty": expected,
                "counted_qty": counted,
                "variance_qty": actual_variance,
                "variance_pct": var_pct,
                "reason_code": reason,
                "counted_by": "cycle_count_team",
                "count_time_min": rng.randint(30, 420),
            }
        )

    return pd.DataFrame.from_records(rows, columns=CYCLE_COUNT_COLUMNS)


def summarize_cycle_counts(cycle_counts: pd.DataFrame) -> pd.DataFrame:
    if cycle_counts is None or cycle_counts.empty:
        return pd.DataFrame(
            [
                {
                    "cycle_counts_total": 0,
                    "lines_with_variance": 0,
                    "line_level_accuracy_pct": 0.0,
                    "net_variance_units": 0,
                    "absolute_variance_units": 0,
                }
            ]
        )

    df = cycle_counts.copy()
    df["variance_qty"] = (
        pd.to_numeric(df["variance_qty"], errors="coerce").fillna(0).astype(int)
    )

    counted = int(df.shape[0])
    with_var = int((df["variance_qty"] != 0).sum())
    accuracy = round((1 - (with_var / counted)) * 100.0, 2) if counted > 0 else 0.0

    net_units = int(df["variance_qty"].sum())
    abs_units = int(df["variance_qty"].abs().sum())

    return pd.DataFrame(
        [
            {
                "cycle_counts_total": counted,
                "lines_with_variance": with_var,
                "line_level_accuracy_pct": accuracy,
                "net_variance_units": net_units,
                "absolute_variance_units": abs_units,
            }
        ]
    )
