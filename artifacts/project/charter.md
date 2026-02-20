# Warehouse Robotics Efficiency Project - Project Charter (Simulation)

## Purpose / Background

Warehouse travel time, slotting, and robotics reliability are major factors of cost and service performance. This project simulates a warehouse environment and demonstrates how analytics and optimization can improve operational KPIs (Power BI) without needing a live WMS or robotics integration, for companies with low budgets or small consulting companies.

## Objective

To create a Warehouse Robotics efficiency system which built around three types of workstreams: Pick path optimization to reduce travel distance. Slotting & Layout strategy to increase the pics from prime locations and cut overall travel time, and a operations control system to monitor robot utilization and downtime while generating alerts to keep the operations running smoothly.

### Scope

The scope is a build demo-ready of a warehouse simulation using a sample 2D grid layout that has defined zones and prime pick location, along with a syntehic SKU's modeled with a volcity distribution with the most drive demand. This will generate sample orders for a simulated operating and computing baseline KPI's to support a clear a before and after comparsion using heatmaps as improvements can implemented and improved.

The project will also have documentation-WBS, a schedule outline, risk, and a change log, plus a demo deliverable as data is exported into CSV's, charts, and a HTML dashboard displaying all the data reports, with a visualization that includes heatmaps and travel paths.

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

Mathmatics (coding)

- Manhattan distance 2D Space: (d= ∣x1 - x2∣ + ∣y1 - y2∣)

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

- Program Data: charter, WBS, schedule outline, risk register, change log
- Data: locations.csv, skus.csv, orders.csv, robot_logs.csv
- Reports: baseline KPIs + route comparison + slotting move list + operation monitoring
- Screenshots/visuals demo (routes, heatmaps, dashboards)

## Timeline (High-Level)

- Week 1: Setup + baseline simulation + program Data
- Week 2: Pick path heuristics + route visualization
- Week 3: Slotting optimization + move list + heatmaps
- Week 4: Fleet control tower KPIs + alerts + ops brief
- Week 5-6: Bug-testing and code optimization
- Weeks 7: README polish + video demo + LinkedIn

## Project Sources

- IDE: Visual Studio Code
- Github: Project storage & Backup
- Canva (Presentation)
- Microsoft: PowerBI, Excel
- Gantt Chart: GanttProject
- draw.io: WBS

## Tech Stack

- IDE: Visual Studio Code
- Github: Project storage & Backup
- CodeX: Bug Fixing & Code Optimization
- Language: Python, HTML, CSS, Json
- Simulation: simpy
- Data + simulation results: pandas
- Charts / KPI plots: matplotlib; PowerBI
- Project packaging: pip + requirements.txt

## Approval

This project is a self-directed portfolio simulation intended to demonstrate skills in operations analytics, WMS concepts, and robotics-oriented warehouse thinking.
