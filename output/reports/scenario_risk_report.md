# Scenario Risk Report (Monte Carlo)

- SLA breach threshold: **>5.00%**

## Top Risk Scenarios (by probability of SLA breach)

- **BASELINE**: P(breach > threshold) **0.00%**, avg breach **0.00%**, avg P95 cycle **5.31 min**
- **DEMAND_SPIKE_2X**: P(breach > threshold) **0.00%**, avg breach **0.00%**, avg P95 cycle **5.39 min**
- **ROBOTS_DOWN_30PCT**: P(breach > threshold) **0.00%**, avg breach **0.00%**, avg P95 cycle **5.80 min**

## Summary Table

`tabulate` is not installed; using CSV-style table fallback.

scenario,runs,avg_sla_breach_pct,avg_p95_cycle_time_min,avg_throughput_orders_per_hour,p95_sla_breach_pct,prob_sla_breach_gt_threshold_pct,p95_of_p95_cycle_time_min,p95_throughput_orders_per_hour
BASELINE,100,0.0,5.31,1.88,0.0,0.0,7.74,1.88
DEMAND_SPIKE_2X,100,0.0,5.39,3.75,0.0,0.0,8.72,3.75
ROBOTS_DOWN_30PCT,100,0.0,5.8,1.88,0.0,0.0,9.39,1.88
HIGH_FAULT_RATE_2X,100,0.0,6.61,1.88,0.0,0.0,11.36,1.88
CONGESTION_PEAK,100,0.0,6.09,2.75,0.0,0.0,11.96,2.75
PERFECT_STORM,100,0.0,6.38,3.75,0.0,0.0,10.96,3.75


## Operational Interpretation

- Higher demand increases queueing and pushes orders closer to (or beyond) due times.
- Reduced robot availability increases wait time via reduced capacity.
- Higher fault rates add variability and tail risk (worse P95s).

## Recommended Mitigations

- Stagger charging and rebalance dispatching to reduce peak congestion.
- Add redundancy: minimum fleet availability threshold or manual fallback playbook.
- Fault hot-spot mitigation: obstacle cleanup, comms checks, and preventive maintenance.
