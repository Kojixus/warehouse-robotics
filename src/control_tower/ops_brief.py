import os
from pathlib import Path

import pandas as pd


def _render_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "_No data._"
    try:
        return df.to_markdown(index=False)
    except Exception:
        # Fallback when optional tabulate dependency is unavailable.
        return "```\n" + df.to_string(index=False) + "\n```"


def write_ops_brief(
    out_path: str,
    fleet_daily: pd.DataFrame,
    by_robot: pd.DataFrame,
    alerts: pd.DataFrame,
    shift_minutes: int = 480,
):
    out_file = Path(out_path)
    os.makedirs(out_file.parent, exist_ok=True)

    fleet_row = (
        fleet_daily.iloc[0].to_dict()
        if fleet_daily is not None and not fleet_daily.empty
        else {}
    )
    by_robot = by_robot.copy() if by_robot is not None else pd.DataFrame()

    if not by_robot.empty and "utilization_pct" in by_robot.columns:
        worst = by_robot.sort_values("utilization_pct", ascending=True).head(1)
        best = by_robot.sort_values("utilization_pct", ascending=False).head(1)
    else:
        worst = pd.DataFrame()
        best = pd.DataFrame()

    top_alerts = alerts.head(5) if alerts is not None and not alerts.empty else pd.DataFrame()

    lines = [
        "# Daily Robotics Ops Brief - Simulated Shift",
        "",
        f"- Shift length: **{shift_minutes} minutes**",
        f"- Fleet size: **{int(fleet_row.get('fleet_size', 0))} robots**",
        "",
        "## Executive Summary",
        "",
        f"- Fleet utilization (avg): **{fleet_row.get('utilization_pct', 0):.1f}%**",
        (
            f"- Downtime (avg): **{fleet_row.get('downtime_pct', 0):.1f}%** | "
            f"Charging (avg): **{fleet_row.get('charging_pct', 0):.1f}%**"
        ),
        (
            f"- Faults per robot: **{fleet_row.get('faults_per_robot', 0):.2f}** | "
            f"MTTR: **{fleet_row.get('mttr_min', 0):.1f} min**"
        ),
        (
            "- Throughput proxy (tasks/hour/robot): "
            f"**{fleet_row.get('tasks_per_hour_proxy', 0):.2f}**"
        ),
        "",
        "## KPI Summary (Fleet)",
        "",
        _render_table(fleet_daily),
        "",
        "## KPI Summary (By Robot)",
        "",
        _render_table(by_robot),
        "",
        "## Top Alerts",
        "",
        _render_table(top_alerts) if not top_alerts.empty else "- No alerts triggered.",
        "",
        "## Notable Robots",
        "",
    ]

    if not worst.empty:
        row = worst.iloc[0]
        lines.append(
            (
                f"- Lowest utilization: **{row['robot_id']}** at **{row['utilization_pct']:.1f}%** "
                f"(faults: {int(row.get('fault_events', 0))}, "
                f"charging: {row.get('charging_pct', 0):.1f}%)"
            )
        )
    if not best.empty:
        row = best.iloc[0]
        lines.append(
            (
                f"- Highest utilization: **{row['robot_id']}** at **{row['utilization_pct']:.1f}%** "
                f"(faults: {int(row.get('fault_events', 0))}, "
                f"charging: {row.get('charging_pct', 0):.1f}%)"
            )
        )
    if worst.empty and best.empty:
        lines.append("- No per-robot KPI data available.")

    lines.extend(
        [
            "",
            "## Root Cause Hypotheses (Simulated)",
            "",
            "- Low utilization windows may indicate demand troughs, charging overlap, or repeated fault recoveries.",
            "- Elevated fault rate may reflect navigation/obstacle issues, battery degradation, or comms instability.",
            "- High simultaneous charging may suggest insufficient charger capacity or poor charge scheduling.",
            "",
            "## Recommended Actions",
            "",
            "- Stagger charge cycles to avoid charging congestion.",
            "- Review top fault codes and add mitigation playbooks.",
            "- Balance dispatching across robots to reduce long idle streaks.",
            "",
        ]
    )

    with out_file.open("w", encoding="utf-8") as fp:
        fp.write("\n".join(lines))
