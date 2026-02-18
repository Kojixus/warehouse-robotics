import os
import platform
import uuid
from datetime import datetime, timezone

import pandas as pd

try:
    from .inventory import (
        apply_slotting_moves_if_present,
        build_abc_classes,
        generate_inventory_snapshot,
        infer_sku_home_locations,
    )
    from .cycle_counts import generate_cycle_counts, summarize_cycle_counts
    from .exceptions import generate_exceptions, summarize_exception_sla
    from .audit_pack import write_evidence_index, write_run_manifest
except ImportError:
    from inventory import (
        apply_slotting_moves_if_present,
        build_abc_classes,
        generate_inventory_snapshot,
        infer_sku_home_locations,
    )
    from cycle_counts import generate_cycle_counts, summarize_cycle_counts
    from exceptions import generate_exceptions, summarize_exception_sla
    from audit_pack import write_evidence_index, write_run_manifest


def _load_csv_resilient(path: str, required_columns: list[str]) -> pd.DataFrame:
    """
    Read CSV files and repair malformed files where each full row is quoted.
    """
    df = pd.read_csv(path)
    if set(required_columns).issubset(df.columns):
        return df

    if df.shape[1] == 1 and "," in str(df.columns[0]):
        repaired_columns = [c.strip().strip('"') for c in str(df.columns[0]).split(",")]
        repaired = df.iloc[:, 0].astype(str).str.strip().str.strip('"').str.split(",", expand=True)
        if repaired.shape[1] == len(repaired_columns):
            repaired.columns = repaired_columns
            df = repaired

    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip().str.strip('"')

    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise ValueError(f"{path} missing required columns: {missing}")
    return df


def ensure_dirs() -> None:
    os.makedirs("data/simulated", exist_ok=True)
    os.makedirs("output/reports", exist_ok=True)
    os.makedirs("output/audit", exist_ok=True)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    skus = _load_csv_resilient("data/simulated/skus.csv", ["sku", "velocity_per_day"])
    locations = _load_csv_resilient("data/simulated/locations.csv", ["location_id"])
    orders = _load_csv_resilient("data/simulated/orders.csv", ["order_id", "sku", "pick_location_id"])

    robot_logs_path = "data/simulated/robot_logs.csv"
    robot_logs = (
        _load_csv_resilient(robot_logs_path, ["state", "timestamp_min", "duration_min"])
        if os.path.exists(robot_logs_path)
        else None
    )

    return skus, locations, orders, robot_logs


def main() -> None:
    ensure_dirs()

    # ---- Config ----
    seed = 42
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"

    # ---- Load inputs ----
    skus, locations, orders, robot_logs = load_inputs()

    # ---- Build ABC + home locations ----
    sku_abc = build_abc_classes(skus)
    sku_home = infer_sku_home_locations(orders, locations)
    sku_home = apply_slotting_moves_if_present(sku_home, "output/reports/move_list_top50.csv")

    # ---- Inventory snapshot ----
    inventory = generate_inventory_snapshot(
        skus=skus,
        sku_abc=sku_abc,
        sku_home_locations=sku_home,
        orders=orders,
        seed=seed,
    )
    inv_path = "data/simulated/inventory_snapshot.csv"
    inventory.to_csv(inv_path, index=False)

    # Inventory accuracy report (high-level)
    inv_accuracy = pd.DataFrame(
        [
            {
                "snapshot_utc": inventory["snapshot_utc"].iloc[0] if not inventory.empty else "",
                "sku_count": int(inventory["sku"].nunique()) if not inventory.empty else 0,
                "total_on_hand_units": int(inventory["on_hand_qty"].sum()) if not inventory.empty else 0,
                "total_reserved_units": int(inventory["reserved_qty"].sum()) if not inventory.empty else 0,
                "total_available_units": int(inventory["available_qty"].sum()) if not inventory.empty else 0,
                "total_inventory_value_est": float((inventory["on_hand_qty"] * inventory["unit_cost"]).sum())
                if not inventory.empty
                else 0.0,
            }
        ]
    )
    inv_accuracy_path = "output/reports/inventory_accuracy.csv"
    inv_accuracy.to_csv(inv_accuracy_path, index=False)

    # ---- Cycle counts ----
    cycle_counts = generate_cycle_counts(
        inventory_snapshot=inventory,
        seed=seed,
        top_n_a=30,
        random_n=20,
    )
    cc_path = "data/simulated/cycle_counts.csv"
    cycle_counts.to_csv(cc_path, index=False)

    cc_results = summarize_cycle_counts(cycle_counts)
    cc_results_path = "output/reports/cycle_count_results.csv"
    cc_results.to_csv(cc_results_path, index=False)

    # ---- Exceptions + SLA ----
    exceptions = generate_exceptions(
        orders=orders,
        inventory_snapshot=inventory,
        robot_logs=robot_logs,
        seed=seed,
    )
    exc_path = "output/reports/exceptions.csv"
    exceptions.to_csv(exc_path, index=False)

    sla = summarize_exception_sla(exceptions)
    sla_path = "output/reports/exception_resolution_sla.csv"
    sla.to_csv(sla_path, index=False)

    # ---- Audit evidence pack ----
    inputs = [
        "data/simulated/locations.csv",
        "data/simulated/skus.csv",
        "data/simulated/orders.csv",
    ]
    if robot_logs is not None:
        inputs.append("data/simulated/robot_logs.csv")
    # Week 3 optional
    if os.path.exists("output/reports/move_list_top50.csv"):
        inputs.append("output/reports/move_list_top50.csv")

    outputs = [
        inv_path,
        cc_path,
        inv_accuracy_path,
        cc_results_path,
        exc_path,
        sla_path,
        "output/audit/run_manifest.json",
        "output/audit/evidence_index.md",
    ]

    write_run_manifest(
        out_path="output/audit/run_manifest.json",
        run_id=run_id,
        seed=seed,
        inputs=inputs,
        outputs=[p for p in outputs if p.endswith(".csv")],
        extra={
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
    )

    write_evidence_index(
        out_path="output/audit/evidence_index.md",
        run_id=run_id,
        seed=seed,
        input_files=inputs,
        key_outputs={
            "Inventory snapshot": inv_path,
            "Cycle counts": cc_path,
            "Inventory accuracy summary": inv_accuracy_path,
            "Cycle count results summary": cc_results_path,
            "Exceptions log": exc_path,
            "Exception SLA summary": sla_path,
            "Run manifest": "output/audit/run_manifest.json",
        },
    )

    print("DONE: Week 5 generated:")
    for p in outputs:
        if os.path.exists(p):
            print(f" - {p}")
        else:
            print(f" - (missing) {p}")


if __name__ == "__main__":
    main()
