import os
import random
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

ETC_TZ = ZoneInfo("Etc/GMT")


def _require_columns(df: pd.DataFrame, required: list[str], frame_name: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{frame_name} missing required columns: {missing}")


def build_abc_classes(skus: pd.DataFrame) -> pd.DataFrame:
    """
    Returns dataframe: sku, velocity_per_day, abc_class
    ABC uses cumulative velocity:
      A <= 80%
      B <= 95%
      C > 95%
    """
    _require_columns(skus, ["sku", "velocity_per_day"], "skus")

    df = skus[["sku", "velocity_per_day"]].copy()
    df["sku"] = df["sku"].astype(str)
    df["velocity_per_day"] = pd.to_numeric(df["velocity_per_day"], errors="coerce").fillna(0.0)
    df = df.sort_values("velocity_per_day", ascending=False).reset_index(drop=True)

    total = float(df["velocity_per_day"].sum())
    df["cum_velocity"] = df["velocity_per_day"].cumsum()
    if total > 0:
        df["cum_pct"] = df["cum_velocity"] / total
    else:
        df["cum_pct"] = 0.0

    def cls(pct: float) -> str:
        if pct <= 0.80:
            return "A"
        if pct <= 0.95:
            return "B"
        return "C"

    df["abc_class"] = df["cum_pct"].apply(cls)
    return df[["sku", "velocity_per_day", "abc_class"]]


def infer_sku_home_locations(orders: pd.DataFrame, locations: pd.DataFrame) -> pd.DataFrame:
    """
    Infers SKU home location from orders history: mode pick_location_id per SKU.
    Returns dataframe: sku, location_id.
    """
    _require_columns(orders, ["sku", "pick_location_id"], "orders")
    _require_columns(locations, ["location_id"], "locations")

    clean = orders[["sku", "pick_location_id"]].dropna().copy()
    if clean.empty:
        return pd.DataFrame(columns=["sku", "location_id"])

    clean["sku"] = clean["sku"].astype(str)
    clean["pick_location_id"] = clean["pick_location_id"].astype(str)

    mode_loc = (
        clean.groupby(["sku", "pick_location_id"], as_index=False)
        .size()
        .sort_values(["sku", "size", "pick_location_id"], ascending=[True, False, True])
        .drop_duplicates("sku", keep="first")
    )

    out = mode_loc[["sku", "pick_location_id"]].rename(columns={"pick_location_id": "location_id"}).copy()
    return out.sort_values("sku").reset_index(drop=True)


def apply_slotting_moves_if_present(sku_home: pd.DataFrame, move_list_path: str) -> pd.DataFrame:
    """
    If Week 3 move list exists, remap sku -> to_location_id.
    """
    if not os.path.exists(move_list_path):
        return sku_home

    moves = pd.read_csv(move_list_path)
    if moves.empty or "sku" not in moves.columns or "to_location_id" not in moves.columns:
        return sku_home

    mapping = (
        moves[["sku", "to_location_id"]]
        .dropna()
        .astype(str)
        .drop_duplicates(subset=["sku"], keep="last")
        .set_index("sku")["to_location_id"]
    )

    out = sku_home.copy()
    out["sku"] = out["sku"].astype(str)
    out["location_id"] = out["location_id"].astype(str)
    out["location_id"] = out["sku"].map(mapping).fillna(out["location_id"]).astype(str)
    return out


def generate_inventory_snapshot(
    skus: pd.DataFrame,
    sku_abc: pd.DataFrame,
    sku_home_locations: pd.DataFrame,
    orders: pd.DataFrame,
    seed: int = 42,
) -> pd.DataFrame:
    _require_columns(skus, ["sku", "velocity_per_day"], "skus")
    _require_columns(sku_abc, ["sku", "abc_class"], "sku_abc")
    _require_columns(sku_home_locations, ["sku", "location_id"], "sku_home_locations")
    _require_columns(orders, ["sku", "pick_location_id"], "orders")

    rng = random.Random(seed)

    # Start from SKU master
    df = skus.copy()
    df["sku"] = df["sku"].astype(str)
    df["velocity_per_day"] = pd.to_numeric(df["velocity_per_day"], errors="coerce").fillna(0.0)

    # Join ABC by sku only to avoid float-join mismatches.
    abc = sku_abc[["sku", "abc_class"]].copy()
    abc["sku"] = abc["sku"].astype(str)
    abc = abc.drop_duplicates(subset=["sku"], keep="first")
    df = df.merge(abc, on="sku", how="left")

    # Join home locations.
    home = sku_home_locations[["sku", "location_id"]].copy()
    home["sku"] = home["sku"].astype(str)
    home["location_id"] = home["location_id"].astype(str)
    home = home.drop_duplicates(subset=["sku"], keep="first")
    df = df.merge(home, on="sku", how="left")

    # Build pool of possible locations from orders and existing assignments.
    order_loc = orders["pick_location_id"].dropna().astype(str)
    known_loc = home["location_id"].dropna().astype(str) if not home.empty else pd.Series(dtype=str)
    loc_pool = pd.concat([order_loc, known_loc], ignore_index=True)
    loc_pool = [x for x in loc_pool.tolist() if x]
    if not loc_pool:
        loc_pool = ["UNASSIGNED"]

    # Assign missing locations.
    df["location_id"] = df["location_id"].fillna("").astype(str)
    missing_loc = df["location_id"].eq("")
    if missing_loc.any():
        df.loc[missing_loc, "location_id"] = [rng.choice(loc_pool) for _ in range(int(missing_loc.sum()))]

    # Reserved qty from open orders demand (sum qty by SKU).
    ord_df = orders.copy()
    ord_df["sku"] = ord_df["sku"].astype(str)
    if "qty" in ord_df.columns:
        ord_df["qty"] = pd.to_numeric(ord_df["qty"], errors="coerce").fillna(1)
        reserved = ord_df.groupby("sku", as_index=False)["qty"].sum().rename(columns={"qty": "reserved_qty"})
    else:
        reserved = ord_df.groupby("sku", as_index=False).size().rename(columns={"size": "reserved_qty"})

    df = df.merge(reserved, on="sku", how="left").fillna({"reserved_qty": 0})
    df["reserved_qty"] = pd.to_numeric(df["reserved_qty"], errors="coerce").fillna(0).astype(int)

    # On-hand qty: days-of-cover * velocity, adjusted by ABC.
    abc_values = df["abc_class"].fillna("C").astype(str).tolist()
    covers = []
    for abc_class in abc_values:
        if abc_class == "A":
            covers.append(rng.randint(7, 14))
        elif abc_class == "B":
            covers.append(rng.randint(5, 10))
        else:
            covers.append(rng.randint(3, 8))

    base_on_hand = (df["velocity_per_day"] * pd.Series(covers)).round().astype(int)

    # Add bounded noise to represent imperfect inventory records.
    noise = pd.Series([rng.randint(-3, 8) for _ in range(len(df))])
    df["on_hand_qty"] = (base_on_hand + noise).clip(lower=0).astype(int)

    # Available
    df["available_qty"] = (df["on_hand_qty"] - df["reserved_qty"]).clip(lower=0).astype(int)

    # Unit cost (for value impact)
    if "unit_cost" in df.columns:
        df["unit_cost"] = pd.to_numeric(df["unit_cost"], errors="coerce").fillna(0.0)
    else:
        df["unit_cost"] = [round(rng.uniform(8.0, 220.0), 2) for _ in range(len(df))]

    # Simple reorder logic
    lead_time_days = pd.Series([rng.randint(3, 7) for _ in range(len(df))])
    safety_stock = pd.Series([rng.randint(5, 40) for _ in range(len(df))])
    df["reorder_point"] = (df["velocity_per_day"] * lead_time_days + safety_stock).round().astype(int)

    target_days = pd.Series([rng.randint(10, 18) for _ in range(len(df))])
    target_stock = (df["velocity_per_day"] * target_days).round().astype(int)
    df["reorder_qty"] = (df["reorder_point"] + target_stock - df["on_hand_qty"]).clip(lower=0).astype(int)

    snapshot_etc = datetime.now(ETC_TZ).strftime("%Y-%m-%dT%H:%M:%S ETC")
    df["snapshot_etc"] = snapshot_etc

    cols = [
        "snapshot_etc",
        "sku",
        "abc_class",
        "velocity_per_day",
        "location_id",
        "on_hand_qty",
        "reserved_qty",
        "available_qty",
        "unit_cost",
        "reorder_point",
        "reorder_qty",
    ]

    df["_abc_sort"] = pd.Categorical(df["abc_class"], categories=["A", "B", "C"], ordered=True)
    return (
        df[cols + ["_abc_sort"]]
        .sort_values(["_abc_sort", "velocity_per_day"], ascending=[True, False], na_position="last")
        .drop(columns=["_abc_sort"])
        .reset_index(drop=True)
    )
