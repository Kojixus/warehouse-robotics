import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

EST_TZ = timezone(timedelta(hours=-5), name="EST")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_entry(path: str) -> dict:
    exists = os.path.exists(path)
    is_file = os.path.isfile(path) if exists else False
    size_bytes = os.path.getsize(path) if is_file else 0
    return {
        "path": path,
        "exists": exists,
        "size_bytes": int(size_bytes),
        "sha256": sha256_file(path) if is_file else "",
    }


def _ensure_parent_dir(out_path: str) -> None:
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def write_run_manifest(
    out_path: str, run_id: str, seed: int, inputs: list, outputs: list, extra: dict
) -> None:
    ts = datetime.now(EST_TZ).strftime("%Y-%m-%dT%H:%M:%S EST")

    manifest = {
        "run_id": run_id,
        "timestamp_est": ts,
        "seed": int(seed),
        "inputs": [_file_entry(path) for path in inputs],
        "outputs": [_file_entry(path) for path in outputs],
        "environment": extra or {},
    }

    _ensure_parent_dir(out_path)
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, indent=2, sort_keys=True)


def write_evidence_index(
    out_path: str, run_id: str, seed: int, input_files: list, key_outputs: dict
) -> None:
    ts = datetime.now(EST_TZ).strftime("%Y-%m-%dT%H:%M:%S EST")

    lines = [
        "# Audit Evidence Index",
        "",
        f"- Run ID: **{run_id}**",
        f"- Timestamp (EST): **{ts}**",
        f"- Seed: **{seed}**",
        "",
        "## Inputs",
        "",
    ]

    for path in input_files:
        lines.append(f"- `{path}`")

    lines.extend(
        [
            "",
            "## Outputs (Evidence)",
            "",
        ]
    )

    for label, path in key_outputs.items():
        lines.append(f"- **{label}:** `{path}`")

    lines.extend(
        [
            "",
            "## What this pack demonstrates",
            "",
            "- Inventory snapshot is reproducible and traceable to specific inputs (SKU master, locations, orders).",
            "- Cycle counts quantify variance and provide an accuracy signal for inventory control.",
            "- Exceptions log captures operational disruptions and enables SLA performance reporting.",
            "- Run manifest provides file hashes for evidence integrity and repeatable verification.",
            "",
        ]
    )

    _ensure_parent_dir(out_path)
    with open(out_path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines))
