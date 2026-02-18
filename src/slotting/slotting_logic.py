from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

PACK_POINT = (0, 0)


def _read_csv_flexible(path: str) -> pd.DataFrame:
    """
    Read CSV files that may be malformed with each row wrapped in double-quotes.
    """
    df = pd.read_csv(path)
    df.columns = [str(c).strip().strip('"') for c in df.columns]

    if len(df.columns) == 1 and "," in str(df.columns[0]):
        raw = pd.read_csv(path, header=None, names=["raw"], dtype=str)
        expanded = (
            raw["raw"]
            .astype(str)
            .str.strip()
            .str.strip('"')
            .str.split(",", expand=True)
        )
        headers = expanded.iloc[0].astype(str).str.strip().tolist()
        expanded = expanded.iloc[1:].reset_index(drop=True)
        expanded.columns = headers
        df = expanded

    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]):
            df[col] = df[col].where(df[col].isna(), df[col].astype(str).str.strip().str.strip('"'))

    return df


def load_data(locations_path: str, skus_path: str, orders_path: str) -> Tuple[pd.DataFrame]:
    locations = _read_csv_flexible(locations_path)
    skus = _read_csv_flexible(skus_path)
    orders = _read_csv_flexible(orders_path)

    # Minimal validation
    for col in ["location_id", "x", "y", "zone", "is_prime"]:
        if col not in locations.columns:
            raise ValueError(f"locations.csv missing column: {col}")

    for col in ["sku", "velocity_per_day"]:
        if col not in skus.columns:
            raise ValueError(f"skus.csv missing column: {col}")

    for col in ["order_id", "sku", "pick_location_id"]:
        if col not in orders.columns:
            raise ValueError(f"orders.csv missing column: {col}")

    # Keep schema types predictable for downstream logic.
    locations["x"] = pd.to_numeric(locations["x"], errors="raise").astype(int)
    locations["y"] = pd.to_numeric(locations["y"], errors="raise").astype(int)
    locations["is_prime"] = pd.to_numeric(locations["is_prime"], errors="coerce").fillna(0).astype(int)
    skus["velocity_per_day"] = pd.to_numeric(skus["velocity_per_day"], errors="coerce").fillna(0.0)

    return locations, skus, orders


def assign_abc_classes(skus: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    df = skus.copy()
    df["velocity_per_day"] = df["velocity_per_day"].astype(float)

    df = df.sort_values("velocity_per_day", ascending=False).reset_index(drop=True)
    df["cum_velocity"] = df["velocity_per_day"].cumsum()
    total = df["velocity_per_day"].sum()
    df["cum_pct"] = df["cum_velocity"] / total if total > 0 else 0

    # ABC cutoffs (common): A=top 80% of velocity, B=next 15%, C=rest
    def classify(cum_pct: float) -> str:
        if cum_pct <= 0.80:
            return "A"
        if cum_pct <= 0.95:
            return "B"
        return "C"

    df["abc_class"] = df["cum_pct"].apply(classify)

    summary = (
        df.groupby("abc_class")
        .agg(
            sku_count=("sku", "count"),
            total_velocity=("velocity_per_day", "sum"),
            avg_velocity=("velocity_per_day", "mean"),
        )
        .reset_index()
        .sort_values("abc_class")
    )

    return df[["sku", "velocity_per_day", "abc_class"]], summary


def infer_current_sku_locations(orders: pd.DataFrame) -> Dict[str, str]:
    # Most frequent pick location per SKU
    mode_loc = (
        orders.groupby(["sku", "pick_location_id"])
        .size()
        .reset_index(name="n")
        .sort_values(["sku", "n"], ascending=[True, False])
        .drop_duplicates("sku")
    )
    return dict(zip(mode_loc["sku"].astype(str), mode_loc["pick_location_id"].astype(str)))


def build_prime_location_list(locations: pd.DataFrame) -> List[str]:
    # Prime locations defined by is_prime flag, then distance to pack
    loc = locations.copy()
    loc["dist_to_pack"] = (loc["x"].astype(int).abs() + loc["y"].astype(int).abs())
    prime = loc[loc["is_prime"] == 1].sort_values("dist_to_pack")
    return prime["location_id"].astype(str).tolist()


def create_slotting_plan(
    locations: pd.DataFrame,
    skus_abc: pd.DataFrame,
    sku_current_loc: Dict[str, str],
    prime_locations: List[str],
    top_n_moves: int = 50,
) -> pd.DataFrame:
    # Choose A SKUs (highest velocities) and place them into prime locations.
    # If a SKU is already in prime, skip.
    skus_a = skus_abc[skus_abc["abc_class"] == "A"].copy()
    skus_a = skus_a.sort_values("velocity_per_day", ascending=False)

    # Current occupant map: location -> sku (inferred from sku_current_loc)
    loc_to_sku = {}
    for sku, loc in sku_current_loc.items():
        loc_to_sku[loc] = sku

    moves = []
    used_prime = set()

    for _, r in skus_a.iterrows():
        sku = str(r["sku"])
        cur_loc = sku_current_loc.get(sku, None)
        if cur_loc is None:
            continue

        # If already in a prime location, no move needed
        if cur_loc in prime_locations:
            used_prime.add(cur_loc)
            continue

        # Find next available prime location not already reserved for an A sku
        target = None
        for p in prime_locations:
            if p in used_prime:
                continue
            target = p
            break

        if target is None:
            break

        used_prime.add(target)

        moves.append({
            "sku": sku,
            "abc_class": "A",
            "velocity_per_day": float(r["velocity_per_day"]),
            "from_location_id": cur_loc,
            "to_location_id": target,
        })

        if len(moves) >= top_n_moves:
            break

    return pd.DataFrame(moves)


def apply_slotting_to_orders(orders: pd.DataFrame, move_list: pd.DataFrame) -> pd.DataFrame:
    df = orders.copy()
    if move_list.empty:
        return df

    # sku -> to_location mapping
    sku_to_new_loc = dict(zip(move_list["sku"].astype(str), move_list["to_location_id"].astype(str)))

    df["pick_location_id"] = df.apply(
        lambda r: sku_to_new_loc.get(str(r["sku"]), str(r["pick_location_id"])),
        axis=1
    )
    return df


def manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def nearest_neighbor(points: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    remaining = points[:]
    route = []
    cur = PACK_POINT
    while remaining:
        nxt = min(remaining, key=lambda p: manhattan(cur, p))
        route.append(nxt)
        remaining.remove(nxt)
        cur = nxt
    return route


def route_distance(points: List[Tuple[int, int]]) -> int:
    if not points:
        return 0
    dist = manhattan(PACK_POINT, points[0])
    for i in range(len(points) - 1):
        dist += manhattan(points[i], points[i + 1])
    dist += manhattan(points[-1], PACK_POINT)
    return dist


def compute_route_kpis_for_orders(locations: pd.DataFrame, orders: pd.DataFrame, method: str = "nearest_neighbor") -> Dict:
    # Build location_id -> (x,y)
    loc_map = dict(zip(locations["location_id"].astype(str), zip(locations["x"].astype(int), locations["y"].astype(int))))

    grouped = orders.groupby("order_id", sort=False)
    dists = []

    for order_id, g in grouped:
        unique_locs = list(dict.fromkeys(g["pick_location_id"].astype(str).tolist()))
        pts = [loc_map[l] for l in unique_locs if l in loc_map]

        if method == "nearest_neighbor":
            route = nearest_neighbor(pts)
            dist = route_distance(route)
        else:
            dist = route_distance(pts)  # fallback

        dists.append(dist)

    avg_dist = float(np.mean(dists)) if dists else 0.0
    return {
        "orders_analyzed": int(len(dists)),
        "avg_distance": avg_dist,
    }


def build_pick_density_grid_from_orders(
    locations: pd.DataFrame,
    orders: pd.DataFrame,
    fill_empty_with_zero: bool = False,
):
    # Count order lines per location
    pick_counts = orders["pick_location_id"].astype(str).value_counts().to_dict()

    loc = locations.copy()
    max_x = int(loc["x"].max())
    max_y = int(loc["y"].max())

    if fill_empty_with_zero:
        grid = np.zeros((max_y + 1, max_x + 1), dtype=float)
    else:
        grid = np.full((max_y + 1, max_x + 1), np.nan)

    for _, r in loc.iterrows():
        lid = str(r["location_id"])
        x, y = int(r["x"]), int(r["y"])
        grid[y, x] = pick_counts.get(lid, 0)

    x0, x1 = int(loc["x"].min()), int(loc["x"].max())
    y0, y1 = int(loc["y"].min()), int(loc["y"].max())

    sub = grid[y0:y1 + 1, x0:x1 + 1]
    x_labels = [str(x) for x in range(x0, x1 + 1)]
    y_labels = [str(y) for y in range(y0, y1 + 1)]
    return sub, x_labels, y_labels
