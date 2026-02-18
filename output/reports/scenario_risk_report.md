# Scenario Risk Report (Monte Carlo)

- SLA breach threshold: **>5.00%**

## Top Risk Scenarios (by probability of SLA breach)

- **BASELINE**: P(breach > threshold) **0.00%**, avg breach **0.00%**, avg P95 cycle **8.77 min**
- **DEMAND_SPIKE_2X**: P(breach > threshold) **0.00%**, avg breach **0.00%**, avg P95 cycle **8.96 min**
- **ROBOTS_DOWN_30PCT**: P(breach > threshold) **0.00%**, avg breach **0.00%**, avg P95 cycle **9.28 min**

## Summary Table

`tabulate` is not installed; using CSV-style table fallback.

scenario,runs,avg_sla_breach_pct,avg_p95_cycle_time_min,avg_throughput_orders_per_hour,p95_sla_breach_pct,prob_sla_breach_gt_threshold_pct,p95_of_p95_cycle_time_min,p95_throughput_orders_per_hour
BASELINE,100,0.0,8.77,1.88,0.0,0.0,11.2,1.88
DEMAND_SPIKE_2X,100,0.0,8.96,3.75,0.0,0.0,11.68,3.75
ROBOTS_DOWN_30PCT,100,0.0,9.28,1.88,0.0,0.0,14.12,1.88
HIGH_FAULT_RATE_2X,100,0.0,9.84,1.88,0.0,0.0,14.16,1.88
CONGESTION_PEAK,100,0.0,9.61,2.75,0.0,0.0,14.73,2.75
PERFECT_STORM,100,0.0,9.49,3.75,0.0,0.0,13.72,3.75


## Operational Interpretation

- Higher demand increases queueing and pushes orders closer to (or beyond) due times.
- Reduced robot availability increases wait time via reduced capacity.
- Higher fault rates add variability and tail risk (worse P95s).

## Recommended Mitigations

- Stagger charging and rebalance dispatching to reduce peak congestion.
- Add redundancy: minimum fleet availability threshold or manual fallback playbook.
- Fault hot-spot mitigation: obstacle cleanup, comms checks, and preventive maintenance.
