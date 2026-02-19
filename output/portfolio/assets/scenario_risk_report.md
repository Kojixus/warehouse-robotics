# Scenario Risk Report (Monte Carlo)

- SLA breach threshold: **>5.00%**

## Top Risk Scenarios (by probability of SLA breach)

- **Compound Disruption Event**: P(breach > threshold) **100.00%**, avg breach **85.53%**, avg P95 cycle **887.54 min**
- **Peak Demand Surge (2x)**: P(breach > threshold) **100.00%**, avg breach **72.36%**, avg P95 cycle **430.58 min**
- **Peak Shift Congestion**: P(breach > threshold) **100.00%**, avg breach **52.99%**, avg P95 cycle **235.80 min**

## Summary Table

`tabulate` is not installed; using CSV-style table fallback.

scenario,runs,avg_sla_breach_pct,avg_p95_cycle_time_min,avg_throughput_orders_per_hour,p95_sla_breach_pct,prob_sla_breach_gt_threshold_pct,p95_of_p95_cycle_time_min,p95_throughput_orders_per_hour
Compound Disruption Event,100,85.53,887.54,200.0,86.44,100.0,903.8,200.0
Peak Demand Surge (2x),100,72.36,430.58,200.0,73.56,100.0,438.14,200.0
Peak Shift Congestion,100,52.99,235.8,150.0,55.09,100.0,243.17,150.0
Fleet Availability Reduction (30%),100,37.79,179.32,100.0,40.88,100.0,188.98,100.0
Elevated Fault Rate (2x),100,0.03,32.4,100.0,0.13,0.0,38.0,100.0
Normal Operations,100,0.0,21.23,100.0,0.0,0.0,25.72,100.0


## Operational Interpretation

- Higher demand increases queueing and pushes orders closer to (or beyond) due times.
- Reduced robot availability increases wait time via reduced capacity.
- Higher fault rates add variability and tail risk (worse P95s).

## Recommended Mitigations

- Stagger charging and rebalance dispatching to reduce peak congestion.
- Add redundancy: minimum fleet availability threshold or manual fallback playbook.
- Fault hot-spot mitigation: obstacle cleanup, comms checks, and preventive maintenance.
