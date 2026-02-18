import pandas as pd


def summarize_runs(per_order: pd.DataFrame, shift_minutes: int) -> pd.DataFrame:
    if per_order.empty:
        return pd.DataFrame()

    keys = ["scenario", "run_index", "seed"]
    grp = per_order.groupby(keys, sort=False)

    agg = grp.agg(
        orders_total=("order_id", "size"),
        on_time_mean=("on_time", "mean"),
        avg_cycle_time_min=("cycle_time_min", "mean"),
        avg_wait_min=("wait_min", "mean"),
    ).reset_index()

    p95_cycle = grp["cycle_time_min"].quantile(0.95).rename("p95_cycle_time_min").reset_index()
    p95_wait = grp["wait_min"].quantile(0.95).rename("p95_wait_min").reset_index()
    out = agg.merge(p95_cycle, on=keys, how="left", sort=False).merge(p95_wait, on=keys, how="left", sort=False)

    out["on_time_pct"] = out["on_time_mean"] * 100.0
    out["sla_breach_pct"] = 100.0 - out["on_time_pct"]

    if shift_minutes > 0:
        out["throughput_orders_per_hour"] = out["orders_total"] / (shift_minutes / 60.0)
    else:
        out["throughput_orders_per_hour"] = 0.0

    out["run_index"] = out["run_index"].astype(int)
    out["seed"] = out["seed"].astype(int)
    out["orders_total"] = out["orders_total"].astype(int)

    out = out[
        [
            "scenario",
            "run_index",
            "seed",
            "orders_total",
            "on_time_pct",
            "sla_breach_pct",
            "avg_cycle_time_min",
            "p95_cycle_time_min",
            "avg_wait_min",
            "p95_wait_min",
            "throughput_orders_per_hour",
        ]
    ]

    for col in [
        "on_time_pct",
        "sla_breach_pct",
        "avg_cycle_time_min",
        "p95_cycle_time_min",
        "avg_wait_min",
        "p95_wait_min",
        "throughput_orders_per_hour",
    ]:
        out[col] = out[col].astype(float).round(2)

    return out.reset_index(drop=True)


def summarize_scenarios(monte: pd.DataFrame, sla_breach_threshold_pct: float) -> pd.DataFrame:
    if monte.empty:
        return pd.DataFrame()

    threshold = float(sla_breach_threshold_pct)
    grp = monte.groupby("scenario", sort=False)

    base = grp.agg(
        runs=("scenario", "size"),
        avg_sla_breach_pct=("sla_breach_pct", "mean"),
        avg_p95_cycle_time_min=("p95_cycle_time_min", "mean"),
        avg_throughput_orders_per_hour=("throughput_orders_per_hour", "mean"),
    ).reset_index()

    p95_sla = grp["sla_breach_pct"].quantile(0.95).rename("p95_sla_breach_pct").reset_index()
    p95_cycle = grp["p95_cycle_time_min"].quantile(0.95).rename("p95_of_p95_cycle_time_min").reset_index()
    p95_thr = grp["throughput_orders_per_hour"].quantile(0.95).rename("p95_throughput_orders_per_hour").reset_index()
    prob_breach = (
        grp["sla_breach_pct"]
        .apply(lambda s: float((s.astype(float) > threshold).mean() * 100.0))
        .rename("prob_sla_breach_gt_threshold_pct")
        .reset_index()
    )

    out = (
        base.merge(p95_sla, on="scenario", how="left", sort=False)
        .merge(prob_breach, on="scenario", how="left", sort=False)
        .merge(p95_cycle, on="scenario", how="left", sort=False)
        .merge(p95_thr, on="scenario", how="left", sort=False)
    )

    out["runs"] = out["runs"].astype(int)
    for col in [
        "avg_sla_breach_pct",
        "p95_sla_breach_pct",
        "prob_sla_breach_gt_threshold_pct",
        "avg_p95_cycle_time_min",
        "p95_of_p95_cycle_time_min",
        "avg_throughput_orders_per_hour",
        "p95_throughput_orders_per_hour",
    ]:
        out[col] = out[col].astype(float).round(2)

    out = out.sort_values(
        ["prob_sla_breach_gt_threshold_pct", "avg_sla_breach_pct"],
        ascending=[False, False],
    ).reset_index(drop=True)
    return out
