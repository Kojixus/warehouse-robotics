# Warehouse Robotics Efficiency Project - Project Charter (Simulation)

## Purpose / Background

Warehouse travel time, slotting, and robotics reliability are major factors of cost and service performance. This project simulates a warehouse environment and demonstrates how analytics and optimization can improve operational KPIs (Power BI) without needing a live WMS or robotics integration, for companies with low budgets or small consulting companies.

## Objective

Create a demo-ready “Warehouse Robotics Efficiency Program” consisting of three workstreams:

1. Pick Path Optimization (reduce travel distance)
2. Slotting & Layout Strategy (increase picks from prime locations; reduce travel time)
3. Robotics Operations Control Tower (monitor utilization/downtime; generate alerts)

## Project Scope

### Scope

- Sample warehouse layout (2D grid) with zones and prime locations
- Sample SKUs with velocity distribution (fast movers drive demand)
- Sample orders for a simulated operating day
- Baseline KPI computation + “before/after” comparisons
- Clear artifacts: WBS, schedule outline, risk register, change log
- Demo outputs: CSVs, charts, short reports (HTML/PDF)
- Provide a heatmap of routes

## Success Metrics (KPIs)

Baseline (Week 1):

- Average travel distance per order (Manhattan distance, grid units)
- Total travel distance per day (grid units)
- Prime zone pick share (%)
- Expedite SLA risk (proxy: % priority-1 orders whose estimated travel exceeds time-to-due)

Later (Weeks 2–4):

- Distance reduction vs baseline (%)
- Picks per hour (proxy)
- Robot utilization (%), downtime (%), MTTR
- Alert rate (alerts/day) and actionability

## Assumptions / Constraints

- Warehouse modeled as a 2D grid; travel uses Manhattan distance.
- All routes start/end at pack/ship point near (0,0).
- Time is proxied from travel distance in Week 1 (not calibrated seconds).
- Congestion and aisle blocking are not modeled initially.
- All datasets are synthetic and reproducible via a fixed random seed.

## Stakeholders / Roles (Simulated)

- Operations Manager (sponsor): approves KPI targets and rollout plan
- WMS Administrator: validates data definitions and process impacts
- Robotics Lead: defines fleet KPIs/alerts and operations cadence
- ICQA Lead: advises inventory accuracy and slotting constraints
- Picking Lead: validates pick strategy practicality

## Deliverables

- Program artifacts: charter, WBS, schedule outline, risk register, change log
- Data artifacts: locations.csv, skus.csv, orders.csv, robot_logs.csv (later)
- Reports: baseline KPIs + route comparison + slotting move list + control tower brief (later)
- Screenshots/visuals for LinkedIn demo (routes, heatmaps, dashboards)

## Timeline (High-Level)

- Week 1: Setup + baseline simulation + program artifacts
- Week 2: Pick path heuristics + route visualization
- Week 3: Slotting optimization + move list + heatmaps
- Week 4: Fleet control tower KPIs + alerts + ops brief
- Weeks 5–6: Packaging + README polish + video demo + LinkedIn posts

## Approval

This project is a self-directed portfolio simulation intended to demonstrate skills in operations analytics, WMS concepts, and robotics-oriented warehouse thinking.
