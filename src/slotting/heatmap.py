import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, Normalize, TwoSlopeNorm


# ----- Heatmap plotting -----

def _label_tick_positions(n_labels: int) -> np.ndarray:
    if n_labels <= 0:
        return np.array([], dtype=int)
    if n_labels == 1:
        return np.array([0], dtype=int)

    # Label every other aisle/bay to keep axis readable.
    step = 2
    ticks = np.arange(0, n_labels, step, dtype=int)
    if ticks[-1] != n_labels - 1:
        ticks = np.append(ticks, n_labels - 1)
    return ticks


def _configure_axis_ticks(ax, x_labels: list, y_labels: list) -> None:
    x_tick_idx = _label_tick_positions(len(x_labels))
    y_tick_idx = _label_tick_positions(len(y_labels))
    ax.set_xticks(x_tick_idx)
    ax.set_yticks(y_tick_idx)
    ax.set_xticklabels([x_labels[i] for i in x_tick_idx])
    ax.set_yticklabels([y_labels[i] for i in y_tick_idx])
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")


def _apply_cell_grid(ax, width: int, height: int, alpha: float = 0.22) -> None:
    ax.set_xticks(np.arange(-0.5, width, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, height, 1), minor=True)
    ax.grid(which="minor", color="#000000", linewidth=0.45, alpha=alpha)
    ax.tick_params(which="minor", bottom=False, left=False)


def plot_annotated_heatmap(
    data_2d: np.ndarray,
    x_labels: list,
    y_labels: list,
    title: str,
    cbar_label: str,
    out_path: str,
) -> None:
    fig, ax = plt.subplots()
    im = ax.imshow(data_2d, origin="lower", cmap="YlOrRd", interpolation="nearest")

    x_tick_idx = _label_tick_positions(len(x_labels))
    y_tick_idx = _label_tick_positions(len(y_labels))
    ax.set_xticks(x_tick_idx)
    ax.set_yticks(y_tick_idx)
    ax.set_xticklabels([x_labels[i] for i in x_tick_idx])
    ax.set_yticklabels([y_labels[i] for i in y_tick_idx])
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    cbar = ax.figure.colorbar(im, ax=ax)
    cbar.ax.set_ylabel(cbar_label, rotation=-90, va="bottom")

    finite_vals = data_2d[np.isfinite(data_2d)]
    vmax = np.max(finite_vals) if finite_vals.size else 0
    threshold = vmax / 2.0 if vmax else 0

    for i in range(data_2d.shape[0]):
        for j in range(data_2d.shape[1]):
            v = data_2d[i, j]
            if np.isnan(v):
                continue
            display_value = int(v) if float(v).is_integer() else round(float(v), 2)
            ax.text(
                j,
                i,
                f"{display_value}",
                ha="center",
                va="center",
                color="white" if v > threshold else "black",
            )

    ax.set_title(title)
    ax.set_xlabel("Aisle")
    ax.set_ylabel("Slot/Bay")
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_annotated_delta_heatmap(
    before_2d: np.ndarray,
    after_2d: np.ndarray,
    x_labels: list,
    y_labels: list,
    title: str,
    cbar_label: str,
    out_path: str,
    top_n_annotations: Optional[int] = None,
) -> None:
    """
    Creates an annotated delta heatmap: (after - before).
    Uses NaN to represent empty/non-location cells.
    Annotates locations by absolute delta ranking.
    Each label includes delta and before/after pick counts.
    """

    # Preserve NaNs from before grid; compute delta elsewhere only where before is valid
    delta = np.where(np.isnan(before_2d), np.nan, after_2d - before_2d)

    height, width = delta.shape
    fig_w = max(8, min(20, width * 0.55))
    fig_h = max(6, min(14, height * 0.55))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    finite_vals = delta[np.isfinite(delta)]
    max_abs = np.max(np.abs(finite_vals)) if finite_vals.size else 1.0
    if max_abs == 0:
        max_abs = 1.0

    # Rich diverging palette for better visual separation of negative/positive deltas.
    cmap = LinearSegmentedColormap.from_list(
        "slotting_impact_diverging",
        [
            "#08306B",
            "#2171B5",
            "#6BAED6",
            "#DEEBF7",
            "#F7F7F7",
            "#FEE0D2",
            "#FC9272",
            "#DE2D26",
            "#7F0000",
        ],
        N=256,
    )
    cmap.set_bad(color="#ff0000")
    masked_delta = np.ma.masked_invalid(delta)
    norm = TwoSlopeNorm(vmin=-max_abs, vcenter=0.0, vmax=max_abs)
    im = ax.imshow(
        masked_delta, origin="lower", cmap=cmap, norm=norm, interpolation="nearest"
    )

    x_tick_idx = _label_tick_positions(len(x_labels))
    y_tick_idx = _label_tick_positions(len(y_labels))
    ax.set_xticks(x_tick_idx)
    ax.set_yticks(y_tick_idx)
    ax.set_xticklabels([x_labels[i] for i in x_tick_idx])
    ax.set_yticklabels([y_labels[i] for i in y_tick_idx])
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    cbar = ax.figure.colorbar(im, ax=ax)
    cbar.ax.set_ylabel(cbar_label, rotation=-90, va="bottom")

    threshold = max_abs / 2.0

    # Rank valid locations by |delta| and then by activity (before+after).
    finite_cells = np.argwhere(np.isfinite(delta))
    if finite_cells.size:
        abs_values = np.abs(delta[finite_cells[:, 0], finite_cells[:, 1]])
        activity_values = (
            before_2d[finite_cells[:, 0], finite_cells[:, 1]]
            + after_2d[finite_cells[:, 0], finite_cells[:, 1]]
        )
        scores = abs_values * 1_000_000 + activity_values
        order = np.argsort(-scores)
        if top_n_annotations is None:
            top_n = len(finite_cells)
        else:
            top_n = max(0, min(top_n_annotations, len(finite_cells)))
        top_cells = finite_cells[order[:top_n]]

        for i, j in top_cells:
            before_v = before_2d[i, j]
            after_v = after_2d[i, j]
            v = delta[i, j]
            display_value = int(v) if float(v).is_integer() else round(float(v), 2)
            value_str = f"{display_value:+}" if display_value != 0 else "+0"
            before_str = (
                int(before_v)
                if float(before_v).is_integer()
                else round(float(before_v), 2)
            )
            after_str = (
                int(after_v)
                if float(after_v).is_integer()
                else round(float(after_v), 2)
            )
            ax.text(
                j,
                i,
                f"{value_str}\n{before_str}->{after_str}",
                ha="center",
                va="center",
                color="white" if abs(v) > threshold else "black",
                fontsize=7,
                linespacing=0.9,
            )

    ax.set_xticks(np.arange(-0.5, len(x_labels), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(y_labels), 1), minor=True)
    ax.grid(which="minor", color="#000000", linewidth=0.7, alpha=0.8)
    ax.tick_params(which="minor", bottom=False, left=False)

    ax.set_title(title)
    ax.set_xlabel("Aisle")
    ax.set_ylabel("Slot/Bay")
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_slotting_story_heatmap(
    before_2d: np.ndarray,
    after_2d: np.ndarray,
    x_labels: list,
    y_labels: list,
    out_path: str,
    top_n_annotations: int = 20,
) -> None:
    """
    Creates a 3-panel slotting story heatmap:
    1) Before pick density
    2) After pick density
    3) Delta (after - before)

    This is designed for portfolio readability:
    - shared scale for before/after for apples-to-apples comparison
    - robust scaling for delta to avoid outlier washout
    - only top-N high-impact cells annotated on delta panel
    """

    delta = np.where(np.isnan(before_2d), np.nan, after_2d - before_2d)
    height, width = delta.shape

    fig_w = max(14, min(26, width * 1.6))
    fig_h = max(6, min(12, height * 0.7))
    fig, axes = plt.subplots(1, 3, figsize=(fig_w, fig_h), constrained_layout=True)

    combined_density = np.concatenate(
        [before_2d[np.isfinite(before_2d)], after_2d[np.isfinite(after_2d)]]
    )
    density_max = np.percentile(combined_density, 98) if combined_density.size else 1.0
    if density_max <= 0:
        density_max = 1.0

    density_norm = Normalize(vmin=0.0, vmax=float(density_max))
    density_cmap = LinearSegmentedColormap.from_list(
        "slotting_density",
        ["#081d58", "#225ea8", "#41b6c4", "#a1dab4", "#ffffcc"],
        N=256,
    )
    density_cmap.set_bad(color="#222222")

    finite_delta = delta[np.isfinite(delta)]
    delta_scale = np.percentile(np.abs(finite_delta), 95) if finite_delta.size else 1.0
    if delta_scale <= 0:
        delta_scale = 1.0

    delta_norm = TwoSlopeNorm(
        vmin=-float(delta_scale), vcenter=0.0, vmax=float(delta_scale)
    )
    delta_cmap = LinearSegmentedColormap.from_list(
        "slotting_delta",
        ["#08306B", "#4292C6", "#F7FBFF", "#FC9272", "#99000D"],
        N=256,
    )
    delta_cmap.set_bad(color="#222222")

    panels = [
        (axes[0], before_2d, "Before Pick Density"),
        (axes[1], after_2d, "After Pick Density"),
        (axes[2], delta, "Delta (After - Before)"),
    ]

    density_im = None
    delta_im = None
    for idx, (ax, grid_data, panel_title) in enumerate(panels):
        masked = np.ma.masked_invalid(grid_data)
        if idx < 2:
            im = ax.imshow(
                masked,
                origin="lower",
                cmap=density_cmap,
                norm=density_norm,
                interpolation="nearest",
            )
            if density_im is None:
                density_im = im
        else:
            im = ax.imshow(
                masked,
                origin="lower",
                cmap=delta_cmap,
                norm=delta_norm,
                interpolation="nearest",
            )
            delta_im = im
        _configure_axis_ticks(ax, x_labels=x_labels, y_labels=y_labels)
        _apply_cell_grid(ax, width=width, height=height)
        ax.set_xlabel("Aisle")
        if idx == 0:
            ax.set_ylabel("Slot/Bay")
        else:
            ax.set_ylabel("")
        ax.set_title(panel_title, fontsize=11)
    if density_im is not None:
        density_cbar = fig.colorbar(
            density_im, ax=[axes[0], axes[1]], fraction=0.025, pad=0.02
        )
        density_cbar.ax.set_ylabel(
            "Pick count (order lines)", rotation=-90, va="bottom"
        )
    if delta_im is not None:
        delta_cbar = fig.colorbar(delta_im, ax=axes[2], fraction=0.046, pad=0.03)
        delta_cbar.ax.set_ylabel("Delta pick count", rotation=-90, va="bottom")

    finite_cells = np.argwhere(np.isfinite(delta))
    if finite_cells.size:
        activity = before_2d + after_2d
        scores = np.abs(delta[finite_cells[:, 0], finite_cells[:, 1]]) * np.sqrt(
            1.0 + activity[finite_cells[:, 0], finite_cells[:, 1]]
        )
        order = np.argsort(-scores)
        top_n = max(0, min(top_n_annotations, len(finite_cells)))
        threshold = delta_scale * 0.4
        for i, j in finite_cells[order[:top_n]]:
            v = float(delta[i, j])
            text_value = f"{v:+.0f}" if float(v).is_integer() else f"{v:+.1f}"
            axes[2].text(
                j,
                i,
                text_value,
                ha="center",
                va="center",
                fontsize=7,
                color="white" if abs(v) > threshold else "black",
            )

    fig.suptitle(
        "Slotting Impact Heatmap: Before vs After vs Delta",
        fontsize=13,
        fontweight="bold",
    )
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def plot_slotting_split_heatmaps(
    before_2d: np.ndarray,
    after_2d: np.ndarray,
    x_labels: list,
    y_labels: list,
    out_before_path: str,
    out_after_path: str,
    out_delta_path: str,
    top_n_annotations: int = 20,
) -> None:
    """
    Writes three separate heatmaps for dashboard layout:
    - before pick density
    - after pick density
    - delta (after - before)
    """

    delta = np.where(np.isnan(before_2d), np.nan, after_2d - before_2d)
    height, width = delta.shape

    combined_density = np.concatenate(
        [before_2d[np.isfinite(before_2d)], after_2d[np.isfinite(after_2d)]]
    )
    density_max = np.percentile(combined_density, 98) if combined_density.size else 1.0
    if density_max <= 0:
        density_max = 1.0

    density_norm = Normalize(vmin=0.0, vmax=float(density_max))
    density_cmap = LinearSegmentedColormap.from_list(
        "slotting_density_split",
        ["#081d58", "#225ea8", "#41b6c4", "#a1dab4", "#ffffcc"],
        N=256,
    )
    density_cmap.set_bad(color="#222222")

    finite_delta = delta[np.isfinite(delta)]
    delta_scale = np.percentile(np.abs(finite_delta), 95) if finite_delta.size else 1.0
    if delta_scale <= 0:
        delta_scale = 1.0

    delta_norm = TwoSlopeNorm(
        vmin=-float(delta_scale), vcenter=0.0, vmax=float(delta_scale)
    )
    delta_cmap = LinearSegmentedColormap.from_list(
        "slotting_delta_split",
        ["#08306B", "#4292C6", "#F7FBFF", "#FC9272", "#99000D"],
        N=256,
    )
    delta_cmap.set_bad(color="#222222")

    def _save_density_panel(data_2d: np.ndarray, title: str, out_path: str) -> None:
        fig_w = max(7, min(13, width * 0.7))
        fig_h = max(5.5, min(10.5, height * 0.7))
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        masked = np.ma.masked_invalid(data_2d)
        im = ax.imshow(
            masked,
            origin="lower",
            cmap=density_cmap,
            norm=density_norm,
            interpolation="nearest",
        )

        _configure_axis_ticks(ax, x_labels=x_labels, y_labels=y_labels)
        _apply_cell_grid(ax, width=width, height=height, alpha=0.24)
        cbar = fig.colorbar(im, ax=ax)
        cbar.ax.set_ylabel("Pick count (order lines)", rotation=-90, va="bottom")

        ax.set_title(title)
        ax.set_xlabel("Aisle")
        ax.set_ylabel("Slot/Bay")
        fig.tight_layout()
        fig.savefig(out_path, dpi=220)
        plt.close(fig)

    def _save_delta_panel(out_path: str) -> None:
        fig_w = max(7, min(13, width * 0.7))
        fig_h = max(5.5, min(10.5, height * 0.7))
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        masked = np.ma.masked_invalid(delta)
        im = ax.imshow(
            masked,
            origin="lower",
            cmap=delta_cmap,
            norm=delta_norm,
            interpolation="nearest",
        )

        _configure_axis_ticks(ax, x_labels=x_labels, y_labels=y_labels)
        _apply_cell_grid(ax, width=width, height=height, alpha=0.24)
        cbar = fig.colorbar(im, ax=ax)
        cbar.ax.set_ylabel("Delta pick count", rotation=-90, va="bottom")

        finite_cells = np.argwhere(np.isfinite(delta))
        if finite_cells.size:
            activity = before_2d + after_2d
            scores = np.abs(delta[finite_cells[:, 0], finite_cells[:, 1]]) * np.sqrt(
                1.0 + activity[finite_cells[:, 0], finite_cells[:, 1]]
            )
            order = np.argsort(-scores)
            top_n = max(0, min(top_n_annotations, len(finite_cells)))
            threshold = delta_scale * 0.4
            for i, j in finite_cells[order[:top_n]]:
                v = float(delta[i, j])
                text_value = f"{v:+.0f}" if float(v).is_integer() else f"{v:+.1f}"
                ax.text(
                    j,
                    i,
                    text_value,
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white" if abs(v) > threshold else "black",
                )

        ax.set_title("Slotting Delta (After - Before)")
        ax.set_xlabel("Aisle")
        ax.set_ylabel("Slot/Bay")
        fig.tight_layout()
        fig.savefig(out_path, dpi=220)
        plt.close(fig)

    _save_density_panel(before_2d, "Slotting Pick Density - Before", out_before_path)
    _save_density_panel(after_2d, "Slotting Pick Density - After", out_after_path)
    _save_delta_panel(out_delta_path)


# ----- Slotting logic -----

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
            df[col] = df[col].where(
                df[col].isna(), df[col].astype(str).str.strip().str.strip('"')
            )

    return df


def load_data(
    locations_path: str, skus_path: str, orders_path: str
) -> Tuple[pd.DataFrame]:
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
    locations["is_prime"] = (
        pd.to_numeric(locations["is_prime"], errors="coerce").fillna(0).astype(int)
    )
    skus["velocity_per_day"] = (
        pd.to_numeric(skus["velocity_per_day"], errors="coerce").fillna(0.0)
    )

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
    return dict(
        zip(mode_loc["sku"].astype(str), mode_loc["pick_location_id"].astype(str))
    )


def build_prime_location_list(locations: pd.DataFrame) -> List[str]:
    # Prime locations defined by is_prime flag, then distance to pack
    loc = locations.copy()
    loc["dist_to_pack"] = loc["x"].astype(int).abs() + loc["y"].astype(int).abs()
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

        moves.append(
            {
                "sku": sku,
                "abc_class": "A",
                "velocity_per_day": float(r["velocity_per_day"]),
                "from_location_id": cur_loc,
                "to_location_id": target,
            }
        )

        if len(moves) >= top_n_moves:
            break

    return pd.DataFrame(moves)


def apply_slotting_to_orders(
    orders: pd.DataFrame, move_list: pd.DataFrame
) -> pd.DataFrame:
    df = orders.copy()
    if move_list.empty:
        return df

    # sku -> to_location mapping
    sku_to_new_loc = dict(
        zip(move_list["sku"].astype(str), move_list["to_location_id"].astype(str))
    )

    df["pick_location_id"] = df.apply(
        lambda r: sku_to_new_loc.get(str(r["sku"]), str(r["pick_location_id"])),
        axis=1,
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


def compute_route_kpis_for_orders(
    locations: pd.DataFrame, orders: pd.DataFrame, method: str = "nearest_neighbor"
) -> Dict:
    # Build location_id -> (x,y)
    loc_map = dict(
        zip(
            locations["location_id"].astype(str),
            zip(locations["x"].astype(int), locations["y"].astype(int)),
        )
    )

    grouped = orders.groupby("order_id", sort=False)
    dists = []

    for _, g in grouped:
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

    sub = grid[y0 : y1 + 1, x0 : x1 + 1]
    x_labels = [str(x) for x in range(x0, x1 + 1)]
    y_labels = [str(y) for y in range(y0, y1 + 1)]
    return sub, x_labels, y_labels


# ----- Runner -----

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "simulated"
OUTPUT_DIR = PROJECT_ROOT / "output"


def ensure_dirs() -> None:
    os.makedirs(OUTPUT_DIR / "reports", exist_ok=True)
    os.makedirs(OUTPUT_DIR / "charts", exist_ok=True)


def main() -> None:
    ensure_dirs()
    for legacy_chart in (
        OUTPUT_DIR / "charts" / "heatmap_before.png",
        OUTPUT_DIR / "charts" / "heatmap_after.png",
        OUTPUT_DIR / "charts" / "heatmap_delta.png",
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
    kpis_before = compute_route_kpis_for_orders(
        locations, orders, method="nearest_neighbor"
    )
    kpis_after = compute_route_kpis_for_orders(
        locations, orders_after, method="nearest_neighbor"
    )

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

    # 7) Slotting impact heatmap (before vs after vs delta)
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

    plot_slotting_split_heatmaps(
        before_2d=before_grid,
        after_2d=after_grid,
        x_labels=x_labels,
        y_labels=y_labels,
        out_before_path=str(OUTPUT_DIR / "charts" / "heatmap_slotting_before.png"),
        out_after_path=str(OUTPUT_DIR / "charts" / "heatmap_slotting_after.png"),
        out_delta_path=str(OUTPUT_DIR / "charts" / "heatmap_slotting_delta.png"),
        top_n_annotations=22,
    )
    plot_slotting_story_heatmap(
        before_2d=before_grid,
        after_2d=after_grid,
        x_labels=x_labels,
        y_labels=y_labels,
        out_path=str(OUTPUT_DIR / "charts" / "heatmap_slotting_impact.png"),
        top_n_annotations=22,
    )

    print("DONE: Week 3 outputs generated:")
    print(" - output/reports/abc_summary.csv")
    print(" - output/reports/move_list_top50.csv")
    print(" - output/reports/slotting_kpis.csv")
    print(" - output/charts/heatmap_slotting_before.png")
    print(" - output/charts/heatmap_slotting_after.png")
    print(" - output/charts/heatmap_slotting_delta.png")
    print(" - output/charts/heatmap_slotting_impact.png")


if __name__ == "__main__":
    main()
