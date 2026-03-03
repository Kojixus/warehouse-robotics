# Scenario Risk Report (Monte Carlo)

- SLA breach threshold: **>5.00%**

## Top Risk Scenarios (by probability of SLA breach)

- **High Demand**: P(breach > threshold) **100.00%**, avg breach **82.98%**, avg P95 cycle **711.73 min**
- **Reduced Robots**: P(breach > threshold) **100.00%**, avg breach **81.37%**, avg P95 cycle **691.89 min**
- **High Faults**: P(breach > threshold) **100.00%**, avg breach **75.08%**, avg P95 cycle **473.27 min**

## Summary Table

`tabulate` is not installed; using CSV-style table fallback.

scenario,runs,avg_sla_breach_pct,avg_p95_cycle_time_min,avg_throughput_orders_per_hour,p95_sla_breach_pct,prob_sla_breach_gt_threshold_pct,p95_of_p95_cycle_time_min,p95_throughput_orders_per_hour
High Demand,200,82.98,711.73,120.0,84.27,100.0,730.18,120.0
Reduced Robots,200,81.37,691.89,100.0,82.12,100.0,711.58,100.0
High Faults,200,75.08,473.27,100.0,76.12,100.0,488.02,100.0
Baseline,200,74.68,465.9,100.0,75.76,100.0,480.61,100.0
Optimized Flow,200,68.4,366.89,95.0,70.26,100.0,379.93,95.0


## Operational Interpretation

- Higher demand increases queueing and pushes orders closer to (or beyond) due times.
- Reduced robot availability increases wait time via reduced capacity.
- Higher fault rates add variability and tail risk (worse P95s).

## Recommended Mitigations

- Stagger charging and rebalance dispatching to reduce peak congestion.
- Add redundancy: minimum fleet availability threshold or manual fallback playbook.
- Fault hot-spot mitigation: obstacle cleanup, comms checks, and preventive maintenance.
