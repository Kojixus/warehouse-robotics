# Daily Robotics Ops Brief - Simulated Shift

- Shift length: **480 minutes**
- Fleet size: **10 robots**

## Executive Summary

- Fleet utilization (avg): **19.6%**
- Downtime (avg): **1.2%** | Charging (avg): **10.5%**
- Faults per robot: **0.70** | MTTR: **5.6 min**
- Throughput proxy (tasks/hour/robot): **1.57**

## KPI Summary (Fleet)

```
 fleet_size  shift_minutes  work_min_total  idle_min_total  charge_min_total  fault_min_total  utilization_pct  downtime_pct  charging_pct  tasks_per_hour_proxy  faults_per_robot  mttr_min
         10            480             940            3299               505               56        19.583333      1.166667     10.520833                 1.575               0.7       5.6
```

## KPI Summary (By Robot)

```
robot_id  WORK  IDLE  CHARGE  FAULT  total_min  utilization_pct  downtime_pct  charging_pct  work_events  tasks_per_hour_proxy  fault_events  mttr_min
     R01   100   326      47      7        480        20.833333      1.458333      9.791667           13                 1.625             1       7.0
     R02    80   353      47      0        480        16.666667      0.000000      9.791667           11                 1.375             0       0.0
     R03    68   366      39      7        480        14.166667      1.458333      8.125000           10                 1.250             1       7.0
     R04   111   323      46      0        480        23.125000      0.000000      9.583333           15                 1.875             0       0.0
     R05   103   319      50      8        480        21.458333      1.666667     10.416667           13                 1.625             1       8.0
     R06    55   367      49      9        480        11.458333      1.875000     10.208333            9                 1.125             1       9.0
     R07   125   289      66      0        480        26.041667      0.000000     13.750000           16                 2.000             0       0.0
     R08   100   311      60      9        480        20.833333      1.875000     12.500000           12                 1.500             1       9.0
     R09    92   334      49      5        480        19.166667      1.041667     10.208333           13                 1.625             1       5.0
     R10   106   311      52     11        480        22.083333      2.291667     10.833333           14                 1.750             1      11.0
```

## Top Alerts

```
 timestamp_min severity         alert_type robot_id                      metric     value  threshold                                                   message
            29     CRIT FLEET_LOW_UTIL_30M          utilization_rolling_30m_pct 50.333333       55.0 Fleet utilization below threshold for a 30-minute window.
            59     CRIT FLEET_LOW_UTIL_30M          utilization_rolling_30m_pct 35.333333       55.0 Fleet utilization below threshold for a 30-minute window.
            89     CRIT FLEET_LOW_UTIL_30M          utilization_rolling_30m_pct 38.333333       55.0 Fleet utilization below threshold for a 30-minute window.
           119     CRIT FLEET_LOW_UTIL_30M          utilization_rolling_30m_pct 43.000000       55.0 Fleet utilization below threshold for a 30-minute window.
           149     CRIT FLEET_LOW_UTIL_30M          utilization_rolling_30m_pct 20.666667       55.0 Fleet utilization below threshold for a 30-minute window.
```

## Notable Robots

- Lowest utilization: **R06** at **11.5%** (faults: 1, charging: 10.2%)
- Highest utilization: **R07** at **26.0%** (faults: 0, charging: 13.8%)

## Root Cause Hypotheses (Simulated)

- Low utilization windows may indicate demand troughs, charging overlap, or repeated fault recoveries.
- Elevated fault rate may reflect navigation/obstacle issues, battery degradation, or comms instability.
- High simultaneous charging may suggest insufficient charger capacity or poor charge scheduling.

## Recommended Actions

- Stagger charge cycles to avoid charging congestion.
- Review top fault codes and add mitigation playbooks.
- Balance dispatching across robots to reduce long idle streaks.
