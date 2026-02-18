import os
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd

MPL_CONFIG_DIR = os.path.join("output", ".matplotlib")
os.makedirs(MPL_CONFIG_DIR, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", MPL_CONFIG_DIR)

import matplotlib.pyplot as plt

PACK_POINT = (0, 0)
RANDOM_SEED = 42

@dataclass(frozen=True)
class Loc:
    x: int
    y: int
    zone: str
    is_prime: int


def manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def route_distance(points: List[Tuple[int, int]]) -> int:
    if not points:
        return 0

    dist = manhattan(PACK_POINT, points[0])
    for i in range(len(points) - 1):
        dist += manhattan(points[i], points[i + 1])
    dist += manhattan(points[-1], PACK_POINT)
    return dist


def nearest_neighbor(points: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    remaining = points[:]
    route: List[Tuple[int, int]] = []
    cur = PACK_POINT
    while remaining:
        nxt = min(remaining, key=lambda p: manhattan(cur, p))
        route.append(nxt)
        remaining.remove(nxt)
        cur = nxt
    return route


def zone_batch(
    points: List[Tuple[int, int]],
    zones: List[str],
    point_to_zone: Dict[Tuple[int, int], str],) -> List[Tuple[int, int]]:
    buckets: Dict[str, List[Tuple[int, int]]] = {zone: [] for zone in zones}
    other: List[Tuple[int, int]] = []
    for point in points:
        zone = point_to_zone.get(point)
        if zone in buckets:
            buckets[zone].append(point)
        else:
            other.append(point)

    route: List[Tuple[int, int]] = []
    cur = PACK_POINT

    for zone in zones:
        zone_points = buckets[zone]
        while zone_points:
            nxt = min(zone_points, key=lambda p: manhattan(cur, p))
            route.append(nxt)
            zone_points.remove(nxt)
            cur = nxt

    while other:
        nxt = min(other, key=lambda p: manhattan(cur, p))
        route.append(nxt)
        other.remove(nxt)
        cur = nxt

    return route


def ensure_dirs() -> None:
    os.makedirs("output/reports", exist_ok=True)
    os.makedirs("output/charts", exist_ok=True)


def read_csv_flexible(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    # Some generators write each CSV row as a single quoted comma-separated string.
    if len(df.columns) == 1 and "," in str(df.columns[0]):
        raw = pd.read_csv(path, header=None, dtype=str).iloc[:, 0]
        split = raw.str.split(",", expand=True)
        header = split.iloc[0].tolist()
        df = split.iloc[1:].copy()
        df.columns = header
        df = df.reset_index(drop=True)

    return df # pyright: ignore[reportReturnType]
def load_locations(path: str) -> Dict[str, Loc]:
    df = read_csv_flexible(path)
    required = {"location_id", "x", "y", "zone", "is_prime"}
    if not required.issubset(df.columns):
        raise ValueError(f"locations.csv missing columns: {required - set(df.columns)}")

    locs: Dict[str, Loc] = {}
    for _, row in df.iterrows():
        loc_id = str(row["location_id"])
        locs[loc_id] = Loc(int(row["x"]), int(row["y"]), str(row["zone"]), int(row["is_prime"]))

    return locs


def load_orders(path: str) -> pd.DataFrame:
    df = read_csv_flexible(path)
    required = {"order_id", "order_time", "due_time", "priority", "sku", "qty", "pick_location_id"}
    if not required.issubset(df.columns):
        raise ValueError(f"orders.csv missing columns: {required - set(df.columns)}")

    df["order_id"] = df["order_id"].astype(str)
    df["sku"] = df["sku"].astype(str)
    df["pick_location_id"] = df["pick_location_id"].astype(str)

    for col in ["order_time", "due_time", "priority", "qty"]:
        df[col] = pd.to_numeric(df[col], errors="raise").astype(int)
    return df
# Plot
def plot_route(
    order_id: str,
    method_name: str,
    route: List[Tuple[int, int]],
    points_all: List[Tuple[int, int]],
    save_path: str,
) -> None:
    xs = [PACK_POINT[0]] + [p[0] for p in route] + [PACK_POINT[0]]
    ys = [PACK_POINT[1]] + [p[1] for p in route] + [PACK_POINT[1]]
    plt.figure()
    plt.scatter([p[0] for p in points_all], [p[1] for p in points_all])
    plt.scatter([PACK_POINT[0]], [PACK_POINT[1]], marker="x")
    plt.plot(xs, ys)
    plt.title(f"{order_id} - {method_name}")
    plt.xlabel("x")
    plt.ylabel("y")
    plt.tight_layout()
    plt.savefig(save_path, dpi=200)
    plt.close()


def main() -> None:
    ensure_dirs()
    rng = random.Random(RANDOM_SEED)
    locs = load_locations("data/simulated/locations.csv")
    orders = load_orders("data/simulated/orders.csv")

    if orders.empty:
        raise ValueError("orders.csv is empty.")
    missing = set(orders["pick_location_id"].astype(str).values.tolist()) - set(locs.keys())
    if missing:
        raise ValueError(f"orders.csv contains unknown pick_location_id(s): {sorted(list(missing))[:10]}")

    # Build point->zone map
    point_to_zone: Dict[Tuple[int, int], str] = {}
    for loc in locs.values():
        point_to_zone[(loc.x, loc.y)] = loc.zone

    grouped = orders.groupby("order_id", sort=False)
    rows = []

    # Choose a sample order to visualize:
    # priority 1 if exists, else first order in file
    p1 = orders[orders["priority"] == 1]
    if len(p1) > 0:
        sample_order_id = str(p1.iloc[0]["order_id"])
    else:
        sample_order_id = str(orders.iloc[0]["order_id"])

    sample_points_all = None
    sample_routes: Dict[str, List[Tuple[int, int]]] = {}

    zone_order = ["A", "B", "C"]

    for order_id, group in grouped:
        order_id = str(order_id)
        # Use unique pick locations for travel (qty does not change walk distance).
        pick_locs = list(dict.fromkeys(group["pick_location_id"].astype(str).tolist()))
        points = [(locs[str(loc_id)].x, locs[str(loc_id)].y) for loc_id in pick_locs]

        points_baseline = points[:]
        rng.shuffle(points_baseline)

        route_nn = nearest_neighbor(points)
        route_zone = zone_batch(points, zone_order, point_to_zone)

        dist_baseline = route_distance(points_baseline)
        dist_nn = route_distance(route_nn)
        dist_zone = route_distance(route_zone)

        best_name, best_dist = min(
            [
                ("nearest_neighbor", dist_nn),
                ("zone_batch", dist_zone),
                ("baseline_random", dist_baseline),
            ],
            key=lambda x: x[1],
        )

        pct_improve = 0.0
        if dist_baseline > 0:
            pct_improve = (dist_baseline - best_dist) / dist_baseline * 100.0

        rows.append(
            {
                "order_id": order_id,
                "num_unique_pick_locations": len(points),
                "distance_baseline_random": dist_baseline,
                "distance_nearest_neighbor": dist_nn,
                "distance_zone_batch": dist_zone,
                "best_method": best_name,
                "best_distance": best_dist,
                "pct_improvement_vs_baseline": round(pct_improve, 2),
            }
        )

        if order_id == sample_order_id:
            sample_points_all = points
            sample_routes["baseline_random"] = points_baseline
            sample_routes["nearest_neighbor"] = route_nn
            sample_routes["zone_batch"] = route_zone

    out_df = pd.DataFrame(rows).sort_values("order_id")
    out_df.to_csv("output/reports/kpi_comparison.csv", index=False)

    summary = {
        "orders": int(out_df.shape[0]),
        "avg_unique_picks_per_order": float(out_df["num_unique_pick_locations"].mean()),
        "avg_distance_baseline": float(out_df["distance_baseline_random"].mean()),
        "avg_distance_nn": float(out_df["distance_nearest_neighbor"].mean()),
        "avg_distance_zone": float(out_df["distance_zone_batch"].mean()),
        "avg_best_distance": float(out_df["best_distance"].mean()),
        "avg_pct_improvement_vs_baseline": float(out_df["pct_improvement_vs_baseline"].mean()),
    }

    # Generate images for the sample order
    if sample_points_all is None:
        raise RuntimeError("Could not select a sample order for plotting.")

    img_baseline = "output/charts/route_baseline.png"
    img_nn = "output/charts/route_nearest_neighbor.png"
    img_zone = "output/charts/route_zone_batch.png"

    plot_route(sample_order_id, "baseline_random", sample_routes["baseline_random"], sample_points_all, img_baseline)
    plot_route(sample_order_id, "nearest_neighbor", sample_routes["nearest_neighbor"], sample_points_all, img_nn)
    plot_route(sample_order_id, "zone_batch", sample_routes["zone_batch"], sample_points_all, img_zone)

    # Basic HTML report
    html = f"""
    <html>
    <head><meta charset=\"utf-8\"><title>Pick Path Report</title></head>
    <body>
      <h1>Pick Path Optimization Report (Week 2 MVP)</h1>
      <p><b>Sample order visualized:</b> {sample_order_id}</p>

      <h2>Summary KPIs</h2>
      <ul>
        <li>Orders analyzed: {summary["orders"]}</li>
        <li>Avg unique picks/order: {summary["avg_unique_picks_per_order"]:.2f}</li>
        <li>Avg distance (baseline random): {summary["avg_distance_baseline"]:.2f}</li>
        <li>Avg distance (nearest neighbor): {summary["avg_distance_nn"]:.2f}</li>
        <li>Avg distance (zone batching): {summary["avg_distance_zone"]:.2f}</li>
        <li>Avg best distance: {summary["avg_best_distance"]:.2f}</li>
        <li>Avg improvement vs baseline: {summary["avg_pct_improvement_vs_baseline"]:.2f}%</li>
      </ul>

      <h2>Route Visuals (sample order)</h2>
      <h3>Baseline (random order)</h3>
      <img src=\"../charts/route_baseline.png\" style=\"max-width:900px;\"><br>

      <h3>Nearest Neighbor</h3>
      <img src=\"../charts/route_nearest_neighbor.png\" style=\"max-width:900px;\"><br>

      <h3>Zone Batching</h3>
      <img src=\"../charts/route_zone_batch.png\" style=\"max-width:900px;\"><br>

      <h2>Outputs</h2>
      <ul>
        <li>KPI table: <code>output/reports/kpi_comparison.csv</code></li>
        <li>Images: <code>output/charts/*.png</code></li>
      </ul>
    </body>
    </html>
    """
    with open("output/reports/pick_path_report.html", "w", encoding="utf-8") as file:
        file.write(html)

    print("DONE ✅")
    print("Generated:")
    print(" - output/reports/kpi_comparison.csv")
    print(" - output/reports/pick_path_report.html")
    print(" - output/charts/route_baseline.png")
    print(" - output/charts/route_nearest_neighbor.png")
    print(" - output/charts/route_zone_batch.png")


if __name__ == "__main__":
    main()
