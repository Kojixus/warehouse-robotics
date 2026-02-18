import os
from pathlib import Path

import pandas as pd

from heatmap_plot import plot_annotated_delta_heatmap
from slotting_logic import (
    apply_slotting_to_orders,
    assign_abc_classes,
    build_pick_density_grid_from_orders,
    build_prime_location_list,
    compute_route_kpis_for_orders,
    create_slotting_plan,
    infer_current_sku_locations,
    load_data,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "simulated"
OUTPUT_DIR = PROJECT_ROOT / "output"


def ensure_dirs() -> None:
    os.makedirs(OUTPUT_DIR / "reports", exist_ok=True)
    os.makedirs(OUTPUT_DIR / "charts", exist_ok=True)


def main() -> None:
    ensure_dirs()
    for legacy_chart in (
        OUTPUT_DIR / "charts" / "heatmap_before_annotated.png",
        OUTPUT_DIR / "charts" / "heatmap_after_annotated.png",
        OUTPUT_DIR / "charts" / "heatmap_delta_annotated.png",
    ):
        legacy_chart.unlink(missing_ok=True)

    locations, skus, orders = load_data(
        str(DATA_DIR / "locations.csv"),
        str(DATA_DIR / "skus.csv"),
        str(DATA_DIR / "orders.csv"),
    )

    # 1) ABC
    skus_abc, abc_summary = assign_abc_classes(skus)
    abc_summary.to_csv(OUTPUT_DIR / "reports" / "abc_summary.csv", index=False)

    # 2) Infer current SKU -> location from order history (mode location)
    sku_current_loc = infer_current_sku_locations(orders)

    # 3) Build list of prime locations (closest to pack point)
    prime_locs = build_prime_location_list(locations)

    # 4) Create slotting plan (move A items into prime locations)
    move_list = create_slotting_plan(
        locations=locations,
        skus_abc=skus_abc,
        sku_current_loc=sku_current_loc,
        prime_locations=prime_locs,
        top_n_moves=50,
    )
    move_list.to_csv(OUTPUT_DIR / "reports" / "move_list_top50.csv", index=False)

    # 5) Apply slotting plan to orders (simulate future state after moves)
    orders_after = apply_slotting_to_orders(orders, move_list)

    # 6) Compute KPIs before/after
    kpis_before = compute_route_kpis_for_orders(locations, orders, method="nearest_neighbor")
    kpis_after = compute_route_kpis_for_orders(locations, orders_after, method="nearest_neighbor")

    slotting_kpis = pd.DataFrame(
        [
            {
                "avg_distance_before": kpis_before["avg_distance"],
                "avg_distance_after": kpis_after["avg_distance"],
                "pct_improvement": round(
                    (kpis_before["avg_distance"] - kpis_after["avg_distance"])
                    / kpis_before["avg_distance"]
                    * 100.0,
                    2,
                )
                if kpis_before["avg_distance"] > 0
                else 0.0,
                "orders_analyzed": kpis_before["orders_analyzed"],
                "method": "nearest_neighbor",
            }
        ]
    )
    slotting_kpis.to_csv(OUTPUT_DIR / "reports" / "slotting_kpis.csv", index=False)

    # 7) Slotting impact heatmap (delta only)
    before_grid, x_labels, y_labels = build_pick_density_grid_from_orders(
        locations,
        orders,
        fill_empty_with_zero=True,
    )
    after_grid, _, _ = build_pick_density_grid_from_orders(
        locations,
        orders_after,
        fill_empty_with_zero=True,
    )

    plot_annotated_delta_heatmap(
        before_2d=before_grid,
        after_2d=after_grid,
        x_labels=x_labels,
        y_labels=y_labels,
        title="Pick Density DELTA (After - Before)",
        cbar_label="Delta pick count (order lines)",
        out_path=str(OUTPUT_DIR / "charts" / "heatmap_slotting_impact.png"),
    )

    print("DONE: Week 3 outputs generated:")
    print(" - output/reports/abc_summary.csv")
    print(" - output/reports/move_list_top50.csv")
    print(" - output/reports/slotting_kpis.csv")
    print(" - output/charts/heatmap_slotting_impact.png")


if __name__ == "__main__":
    main()
