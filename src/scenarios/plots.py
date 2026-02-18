import os
import pandas as pd

MPL_CONFIG_DIR = os.path.join("output", ".matplotlib")
os.makedirs(MPL_CONFIG_DIR, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", MPL_CONFIG_DIR)

import matplotlib.pyplot as plt


def _prep_plot_data(summary: pd.DataFrame, value_col: str) -> pd.DataFrame:
    if summary.empty or "scenario" not in summary.columns or value_col not in summary.columns:
        return pd.DataFrame(columns=["scenario", value_col])

    out = summary.loc[:, ["scenario", value_col]].copy()
    out["scenario"] = out["scenario"].astype(str)
    out[value_col] = pd.to_numeric(out[value_col], errors="coerce").fillna(0.0)
    return out.sort_values(value_col, ascending=False).reset_index(drop=True)


def _plot_bar(summary: pd.DataFrame, value_col: str, title: str, ylabel: str, out_path: str):
    df = _prep_plot_data(summary, value_col=value_col)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 5))
    if df.empty:
        ax.text(0.5, 0.5, "No scenario data available", ha="center", va="center")
        ax.set_axis_off()
    else:
        ax.bar(df["scenario"], df[value_col])
        ax.set_title(title)
        ax.set_xlabel("Scenario")
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="x", rotation=45)
        for tick in ax.get_xticklabels():
            tick.set_ha("right")

    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_sla_breach_probability(summary: pd.DataFrame, out_path: str):
    _plot_bar(
        summary=summary,
        value_col="prob_sla_breach_gt_threshold_pct",
        title="Probability SLA Breach > Threshold (Monte Carlo)",
        ylabel="Probability (%)",
        out_path=out_path,
    )


def plot_cycle_time_p95(summary: pd.DataFrame, out_path: str):
    _plot_bar(
        summary=summary,
        value_col="avg_p95_cycle_time_min",
        title="Avg P95 Order Cycle Time by Scenario",
        ylabel="P95 Cycle Time (min)",
        out_path=out_path,
    )


def plot_throughput(summary: pd.DataFrame, out_path: str):
    _plot_bar(
        summary=summary,
        value_col="avg_throughput_orders_per_hour",
        title="Avg Throughput by Scenario",
        ylabel="Orders / hour",
        out_path=out_path,
    )
