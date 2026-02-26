from __future__ import annotations

import platform
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

EST_TZ = timezone(timedelta(hours=-5), name="EST")

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

DATA_DIR = Path("data/simulated")
OUTPUT_REPORTS_DIR = Path("output/reports")
OUTPUT_AUDIT_DIR = Path("output/audit")
SLOTTING_MOVE_LIST_PATH = OUTPUT_REPORTS_DIR / "move_list_top50.csv"
ROBOT_LOG_CANDIDATES: tuple[Path, ...] = (
    DATA_DIR / "robot_logs.csv",
    Path("output/operations_data/simulated/robot_logs.csv"),
    Path("output/control_tower_data/simulated/robot_logs.csv"),
    Path("output/simulated/robot_logs.csv"),
)


def _load_csv_resilient(path: Path, required_columns: list[str]) -> pd.DataFrame:
    """
    Read CSV files and repair malformed files where each full row is quoted.
    """
    df = pd.read_csv(path)
    if set(required_columns).issubset(df.columns):
        return df

    if df.shape[1] == 1 and "," in str(df.columns[0]):
        repaired_columns = [c.strip().strip('"') for c in str(df.columns[0]).split(",")]
        repaired = (
            df.iloc[:, 0]
            .astype(str)
            .str.strip()
            .str.strip('"')
            .str.split(",", expand=True)
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
        raise ValueError(f"{path.as_posix()} missing required columns: {missing}")
    return df


def ensure_dirs() -> None:
    for folder in (DATA_DIR, OUTPUT_REPORTS_DIR, OUTPUT_AUDIT_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def resolve_robot_logs_path() -> Path | None:
    for path in ROBOT_LOG_CANDIDATES:
        if path.exists():
            return path
    return None


def load_inputs() -> (
    tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame | None, Path | None]
):
    skus = _load_csv_resilient(DATA_DIR / "skus.csv", ["sku", "velocity_per_day"])
    locations = _load_csv_resilient(DATA_DIR / "locations.csv", ["location_id"])
    orders = _load_csv_resilient(
        DATA_DIR / "orders.csv", ["order_id", "sku", "pick_location_id"]
    )

    robot_logs_path = resolve_robot_logs_path()
    robot_logs = (
        _load_csv_resilient(robot_logs_path, ["state", "timestamp_min", "duration_min"])
        if robot_logs_path
        else None
    )

    return skus, locations, orders, robot_logs, robot_logs_path


def main() -> None:
    ensure_dirs()

    # ---- Config ----
    seed = 42
    run_id = f"run_{datetime.now(EST_TZ).strftime('%Y%m%dT%H%M%S')}EST_{uuid.uuid4().hex[:8]}"

    # ---- Load inputs ----
    skus, locations, orders, robot_logs, robot_logs_path = load_inputs()
    if robot_logs_path:
        print(f"Using robot logs: {robot_logs_path.as_posix()}")
    else:
        print("Using robot logs: none found (ROBOT_DELAY signal disabled)")

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
    inv_path = DATA_DIR / "inventory_snapshot.csv"
    inventory.to_csv(inv_path, index=False)

    # Inventory accuracy report (high-level)
    inv_accuracy = pd.DataFrame(
        [
            {
                "snapshot_est": (
                    inventory["snapshot_est"].iloc[0] if not inventory.empty else ""
                ),
                "sku_count": (
                    int(inventory["sku"].nunique()) if not inventory.empty else 0
                ),
                "total_on_hand_units": (
                    int(inventory["on_hand_qty"].sum()) if not inventory.empty else 0
                ),
                "total_reserved_units": (
                    int(inventory["reserved_qty"].sum()) if not inventory.empty else 0
                ),
                "total_available_units": (
                    int(inventory["available_qty"].sum()) if not inventory.empty else 0
                ),
                "total_inventory_value_est": (
                    float((inventory["on_hand_qty"] * inventory["unit_cost"]).sum())
                    if not inventory.empty
                    else 0.0
                ),
            }
        ]
    )
    inv_accuracy_path = OUTPUT_REPORTS_DIR / "inventory_accuracy.csv"
    inv_accuracy.to_csv(inv_accuracy_path, index=False)

    # ---- Cycle counts ----
    cycle_counts = generate_cycle_counts(
        inventory_snapshot=inventory,
        seed=seed,
        top_n_a=30,
        random_n=20,
    )
    cycle_counts_path = DATA_DIR / "cycle_counts.csv"
    cycle_counts.to_csv(cycle_counts_path, index=False)

    cycle_count_results = summarize_cycle_counts(cycle_counts)
    cycle_count_results_path = OUTPUT_REPORTS_DIR / "cycle_count_results.csv"
    cycle_count_results.to_csv(cycle_count_results_path, index=False)

    # ---- Exceptions + SLA ----
    exceptions = generate_exceptions(
        orders=orders,
        inventory_snapshot=inventory,
        robot_logs=robot_logs,
        seed=seed,
    )
    exceptions_path = OUTPUT_REPORTS_DIR / "exceptions.csv"
    exceptions.to_csv(exceptions_path, index=False)

    exception_sla = summarize_exception_sla(exceptions)
    exception_sla_path = OUTPUT_REPORTS_DIR / "exception_resolution_sla.csv"
    exception_sla.to_csv(exception_sla_path, index=False)

    # ---- Audit evidence pack ----
    inputs = [
        DATA_DIR / "locations.csv",
        DATA_DIR / "skus.csv",
        DATA_DIR / "orders.csv",
    ]
    if robot_logs is not None and robot_logs_path:
        inputs.append(robot_logs_path)
    if SLOTTING_MOVE_LIST_PATH.exists():
        inputs.append(SLOTTING_MOVE_LIST_PATH)

    run_manifest_path = OUTPUT_AUDIT_DIR / "run_manifest.json"
    evidence_index_path = OUTPUT_AUDIT_DIR / "evidence_index.md"

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
        outputs=[path.as_posix() for path in outputs if path.suffix.lower() == ".csv"],
        extra={
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
    )

    write_evidence_index(
        out_path=evidence_index_path.as_posix(),
        run_id=run_id,
        seed=seed,
        input_files=[path.as_posix() for path in inputs],
        key_outputs={
            "Inventory snapshot": inv_path.as_posix(),
            "Cycle counts": cycle_counts_path.as_posix(),
            "Inventory accuracy summary": inv_accuracy_path.as_posix(),
            "Cycle count results summary": cycle_count_results_path.as_posix(),
            "Exceptions log": exceptions_path.as_posix(),
            "Exception SLA summary": exception_sla_path.as_posix(),
            "Run manifest": run_manifest_path.as_posix(),
        },
    )

    print("DONE: Week 5 generated:")
    for path in outputs:
        if path.exists():
            print(f" - {path.as_posix()}")
        else:
            print(f" - (missing) {path.as_posix()}")


if __name__ == "__main__":
    main()
