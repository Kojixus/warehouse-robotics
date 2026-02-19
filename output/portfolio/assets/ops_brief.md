# Daily Robotics Ops Brief - Simulated Shift

- Shift length: **480 minutes**
- Fleet size: **10 robots**

## Executive Summary

- Fleet utilization (avg): **41.6%**
- Downtime (avg): **3.0%** | Charging (avg): **16.1%**
- Faults per robot: **1.60** | MTTR: **7.5 min**
- Throughput proxy (tasks/hour/robot): **3.34**

## KPI Summary (Fleet)

```
 fleet_size  shift_minutes  work_min_total  idle_min_total  charge_min_total  fault_min_total  utilization_pct  downtime_pct  charging_pct  tasks_per_hour_proxy  faults_per_robot  mttr_min
         10            480            1997            1887               771              145        41.604167      3.020833       16.0625                3.3375               1.6       7.5
```

## KPI Summary (By Robot)

```
robot_id  WORK  IDLE  CHARGE  FAULT  total_min  utilization_pct  downtime_pct  charging_pct  work_events  tasks_per_hour_proxy  fault_events  mttr_min
     R01   207   182      81     10        480        43.125000      2.083333     16.875000           28                 3.500             1      10.0
     R02   214   161      89     16        480        44.583333      3.333333     18.541667           25                 3.125             2       8.0
     R03   222   169      89      0        480        46.250000      0.000000     18.541667           29                 3.625             0       0.0
     R04   175   203      78     24        480        36.458333      5.000000     16.250000           26                 3.250             3       8.0
     R05   215   163      92     10        480        44.791667      2.083333     19.166667           29                 3.625             1      10.0
     R06   176   212      69     23        480        36.666667      4.791667     14.375000           22                 2.750             2      11.5
     R07   187   215      78      0        480        38.958333      0.000000     16.250000           25                 3.125             0       0.0
     R08   186   208      71     15        480        38.750000      3.125000     14.791667           28                 3.500             2       7.5
     R09   198   211      60     11        480        41.250000      2.291667     12.500000           28                 3.500             1      11.0
     R10   217   163      64     36        480        45.208333      7.500000     13.333333           27                 3.375             4       9.0
```

## Top Alerts

```
 timestamp_min severity         alert_type robot_id                      metric     value  threshold                                                   message
            37     CRIT FLEET_LOW_UTIL_30M          utilization_rolling_30m_pct 54.666667       55.0 Fleet utilization below threshold for a 30-minute window.
            67     CRIT FLEET_LOW_UTIL_30M          utilization_rolling_30m_pct 40.666667       55.0 Fleet utilization below threshold for a 30-minute window.
            97     CRIT FLEET_LOW_UTIL_30M          utilization_rolling_30m_pct 43.333333       55.0 Fleet utilization below threshold for a 30-minute window.
           127     CRIT FLEET_LOW_UTIL_30M          utilization_rolling_30m_pct 36.666667       55.0 Fleet utilization below threshold for a 30-minute window.
           157     CRIT FLEET_LOW_UTIL_30M          utilization_rolling_30m_pct 38.666667       55.0 Fleet utilization below threshold for a 30-minute window.
```

## Notable Robots

- Lowest utilization: **R04** at **36.5%** (faults: 3, charging: 16.2%)
- Highest utilization: **R03** at **46.2%** (faults: 0, charging: 18.5%)

## Root Cause Hypotheses (Simulated)

- Low utilization windows may indicate demand troughs, charging overlap, or repeated fault recoveries.
- Elevated fault rate may reflect navigation/obstacle issues, battery degradation, or comms instability.
- High simultaneous charging may suggest insufficient charger capacity or poor charge scheduling.

## Recommended Actions

- Stagger charge cycles to avoid charging congestion.
- Review top fault codes and add mitigation playbooks.
- Balance dispatching across robots to reduce long idle streaks.
