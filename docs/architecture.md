# Architecture

```mermaid
flowchart LR
  A[Data Inputs<br/>locations.csv<br/>skus.csv<br/>orders.csv] --> B[Week 2<br/>Pick Path]
  A --> C[Week 3<br/>Slotting]
  A --> D[Week 4<br/>Control Tower<br/>robot_logs.csv]
  A --> E[Week 5<br/>Audit Pack]
  D --> F[Week 6<br/>Scenario Risk]
  B --> G[Reports and Charts]
  C --> G
  D --> G
  E --> G
  F --> G
  G --> H[Week 7<br/>Portfolio Pack<br/>dashboard.html]
```

## Pipeline order
1. `python src/pick_path/analyze_routes.py`
2. `python src/slotting/run_slotting.py`
3. `python src/control_tower/run_control_tower.py`
4. `python src/scenarios/run_scenarios.py`
5. `python src/audit_ready/run_audit_pack.py`
6. `python src/portfolio/run_portfolio_pack.py`

## Single command entrypoint
Run all steps with:

```bash
python main.py
```

## Key outputs
- `output/reports/*.csv`
- `output/charts/*.png`
- `output/audit/run_manifest.json`
- `output/portfolio/dashboard.html`
