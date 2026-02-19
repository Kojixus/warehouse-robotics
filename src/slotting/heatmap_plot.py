import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm, Normalize
from typing import Optional


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
    """
    Creates an annotated heatmap.
    Uses NaN to represent empty/non-location cells.
    Annotates only finite cells.
    """

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
    im = ax.imshow(masked_delta, origin="lower", cmap=cmap, norm=norm, interpolation="nearest")

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
            before_str = int(before_v) if float(before_v).is_integer() else round(float(before_v), 2)
            after_str = int(after_v) if float(after_v).is_integer() else round(float(after_v), 2)
            ax.text(
                j,
                i,
                f"{value_str}\n{before_str}->{after_str}",
                ha="center", va="center",
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

    delta_norm = TwoSlopeNorm(vmin=-float(delta_scale), vcenter=0.0, vmax=float(delta_scale))
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
            im = ax.imshow(masked, origin="lower", cmap=density_cmap, norm=density_norm, interpolation="nearest")
            if density_im is None:
                density_im = im
        else:
            im = ax.imshow(masked, origin="lower", cmap=delta_cmap, norm=delta_norm, interpolation="nearest")
            delta_im = im
        _configure_axis_ticks(ax, x_labels=x_labels, y_labels=y_labels)
        _apply_cell_grid(ax, width=width, height=height)
        ax.set_xlabel("Aisle")
        if idx == 0:
            ax.set_ylabel("Slot/Bay")
        else:
            ax.set_ylabel("")
        ax.set_title(panel_title, fontsize=11)
    density_cbar = fig.colorbar(density_im, ax=[axes[0], axes[1]], fraction=0.025, pad=0.02)
    density_cbar.ax.set_ylabel("Pick count (order lines)", rotation=-90, va="bottom")
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

    delta_norm = TwoSlopeNorm(vmin=-float(delta_scale), vcenter=0.0, vmax=float(delta_scale))
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
        im = ax.imshow(masked, origin="lower", cmap=density_cmap, norm=density_norm, interpolation="nearest")

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
        im = ax.imshow(masked, origin="lower", cmap=delta_cmap, norm=delta_norm, interpolation="nearest")

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
