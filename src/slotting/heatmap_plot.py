import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
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
