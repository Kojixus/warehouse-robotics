from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "output"
PORTFOLIO_DIR = OUTPUT_DIR / "portfolio"
ASSETS_DIR = PORTFOLIO_DIR / "assets"
DOCS_DIR = PROJECT_ROOT / "docs"

EXPECTED_FILES: dict[str, str] = {
    "Pick Path KPI Comparison": "output/reports/kpi_comparison.csv",
    "Pick Path Report (HTML)": "output/reports/pick_path_report.html",
    "Route Baseline": "output/charts/route_baseline.png",
    "Route Nearest Neighbor": "output/charts/route_nearest_neighbor.png",
    "Route Zone Batch": "output/charts/route_zone_batch.png",
    "ABC Summary": "output/reports/abc_summary.csv",
    "Move List Top 50": "output/reports/move_list_top50.csv",
    "Slotting KPIs": "output/reports/slotting_kpis.csv",
    "Slotting Impact Heatmap": "output/charts/heatmap_slotting_impact.png",
    "Fleet KPIs Daily": "output/reports/fleet_daily_kpis.csv",
    "Fleet KPIs by Robot": "output/reports/robot_kpis.csv",
    "Alerts": "output/reports/alerts.csv",
    "Ops Brief": "output/reports/ops_brief.md",
    "Utilization Chart": "output/charts/utilization_over_time.png",
    "Faults Chart": "output/charts/faults_over_time.png",
    "Evidence Index": "output/audit/evidence_index.md",
    "Run Manifest": "output/audit/run_manifest.json",
    "Inventory Accuracy": "output/reports/inventory_accuracy.csv",
    "Cycle Count Results": "output/reports/cycle_count_results.csv",
    "Exceptions": "output/reports/exceptions.csv",
    "Exception SLA": "output/reports/exception_resolution_sla.csv",
    "Scenario Definitions": "output/reports/scenario_definitions.csv",
    "Scenario Summary": "output/reports/scenario_summary.csv",
    "Scenario Risk Report": "output/reports/scenario_risk_report.md",
    "SLA Breach Probability": "output/charts/sla_breach_probability.png",
    "Cycle Time P95": "output/charts/cycle_time_p95_by_scenario.png",
    "Throughput": "output/charts/throughput_by_scenario.png",
}


def ensure_dirs() -> None:
    PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)


def project_path(relative_path: str) -> Path:
    return PROJECT_ROOT / relative_path


def safe_read_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None

    try:
        df = pd.read_csv(path)
        if len(df.columns) == 1 and "," in str(df.columns[0]):
            raw = pd.read_csv(path, header=None, dtype=str).iloc[:, 0]
            split = raw.str.split(",", expand=True)
            header = split.iloc[0].tolist()
            df = split.iloc[1:].copy()
            df.columns = header
            df = df.reset_index(drop=True)
        return df  # pyright: ignore[reportReturnType]
    except Exception:
        return None


def copy_asset(src: Path, out_name: str | None = None) -> str:
    if not src.exists():
        return ""

    dest_name = out_name or src.name
    dest = ASSETS_DIR / dest_name
    shutil.copy2(src, dest)
    return dest.relative_to(PORTFOLIO_DIR).as_posix()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def html_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def df_to_html_table(df: pd.DataFrame | None, max_rows: int = 25) -> str:
    if df is None or df.empty:
        return "<p class='muted'>No data found.</p>"
    return df.head(max_rows).to_html(index=False, classes="table", border=0)


def first_numeric(df: pd.DataFrame | None, column: str) -> float | None:
    if df is None or df.empty or column not in df.columns:
        return None
    try:
        return float(pd.to_numeric(df[column], errors="coerce").dropna().iloc[0])
    except Exception:
        return None


def format_metric(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "-"
    return f"{value:,.2f}{suffix}"


def image_block(src: str, alt: str, missing_note: str = "") -> str:
    if src:
        return f"<img src=\"{src}\" alt=\"{html_escape(alt)}\"/>"
    if missing_note:
        return f"<p class='muted'>{html_escape(missing_note)}</p>"
    return ""


def link_block(src: str, label: str) -> str:
    if not src:
        return ""
    safe_label = html_escape(label)
    return f"<div><a href=\"{src}\">{safe_label}</a></div>"


def build_dashboard() -> tuple[str, list[str]]:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    kpi_comp = safe_read_csv(project_path(EXPECTED_FILES["Pick Path KPI Comparison"]))
    slot_kpis = safe_read_csv(project_path(EXPECTED_FILES["Slotting KPIs"]))
    fleet_daily = safe_read_csv(project_path(EXPECTED_FILES["Fleet KPIs Daily"]))
    inv_acc = safe_read_csv(project_path(EXPECTED_FILES["Inventory Accuracy"]))
    exc_sla = safe_read_csv(project_path(EXPECTED_FILES["Exception SLA"]))
    scen_summary = safe_read_csv(project_path(EXPECTED_FILES["Scenario Summary"]))

    image_keys = [
        "Route Baseline",
        "Route Nearest Neighbor",
        "Route Zone Batch",
        "Slotting Impact Heatmap",
        "Utilization Chart",
        "Faults Chart",
        "SLA Breach Probability",
        "Cycle Time P95",
        "Throughput",
    ]
    image_paths: dict[str, str] = {}
    for key in image_keys:
        image_paths[key] = copy_asset(project_path(EXPECTED_FILES[key]))

    evidence_index_local = copy_asset(project_path(EXPECTED_FILES["Evidence Index"]))
    run_manifest_local = copy_asset(project_path(EXPECTED_FILES["Run Manifest"]))
    ops_brief_local = copy_asset(project_path(EXPECTED_FILES["Ops Brief"]))
    risk_report_local = copy_asset(project_path(EXPECTED_FILES["Scenario Risk Report"]))

    fleet_util = first_numeric(fleet_daily, "utilization_pct")
    fleet_downtime = first_numeric(fleet_daily, "downtime_pct")
    inv_value = first_numeric(inv_acc, "total_inventory_value_est")

    top_risk_pct: float | None = None
    top_risk_name = "n/a"
    if (
        scen_summary is not None
        and not scen_summary.empty
        and "prob_sla_breach_gt_threshold_pct" in scen_summary.columns
    ):
        risk_series = pd.to_numeric(scen_summary["prob_sla_breach_gt_threshold_pct"], errors="coerce")
        valid = scen_summary.assign(_risk=risk_series).dropna(subset=["_risk"])
        if not valid.empty:
            idx = valid["_risk"].idxmax()
            top_row = valid.loc[idx]
            top_risk_pct = float(top_row["_risk"])
            if "scenario" in valid.columns:
                top_risk_name = str(top_row["scenario"])

    missing_inputs = [
        f"{label}: {rel_path}"
        for label, rel_path in EXPECTED_FILES.items()
        if not project_path(rel_path).exists()
    ]

    week2_images = "\n".join(
        [
            image_block(image_paths["Route Baseline"], "Route baseline", "Route charts not found."),
            image_block(image_paths["Route Nearest Neighbor"], "Route nearest neighbor"),
            image_block(image_paths["Route Zone Batch"], "Route zone batch"),
        ]
    )

    week4_images = "\n".join(
        [
            image_block(image_paths["Utilization Chart"], "Utilization over time"),
            image_block(image_paths["Faults Chart"], "Faults over time"),
        ]
    )

    missing_html = ""
    if missing_inputs:
        missing_items = "".join(
            f"<li><code>{html_escape(item)}</code></li>" for item in missing_inputs
        )
        missing_html = f"""
        <div class=\"card span-12\">
          <h2>Missing Inputs</h2>
          <p class=\"muted\">Dashboard generated with partial data. Missing artifacts:</p>
          <ul>{missing_items}</ul>
        </div>
        """

    css = """
    :root {
      --bg: #0b0f14;
      --card: #111823;
      --line: #1f2a37;
      --text: #e6eaf2;
      --muted: #98a2b3;
      --accent: #7dd3fc;
    }
    body {
      margin: 0;
      font-family: "Segoe UI", Tahoma, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    .wrap {
      max-width: 1120px;
      margin: 0 auto;
      padding: 24px 16px 48px;
    }
    .title h1 {
      margin: 0;
      font-size: 28px;
    }
    .title p {
      margin: 8px 0 0;
      color: var(--muted);
    }
    .pill {
      display: inline-block;
      margin-top: 12px;
      border: 1px solid rgba(125, 211, 252, 0.35);
      color: var(--accent);
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      background: rgba(125, 211, 252, 0.12);
    }
    .grid {
      margin-top: 16px;
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 12px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
    }
    .card h2 {
      margin: 0 0 10px;
      font-size: 15px;
    }
    .muted {
      color: var(--muted);
    }
    .kpi {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    .kpi .box {
      min-width: 165px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #0d1420;
      padding: 10px;
    }
    .kpi .l {
      color: var(--muted);
      font-size: 12px;
    }
    .kpi .v {
      margin-top: 4px;
      font-size: 18px;
      font-weight: 700;
    }
    .table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    .table th,
    .table td {
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      padding: 6px;
    }
    img {
      margin-top: 8px;
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #0b0f14;
    }
    a {
      color: var(--accent);
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
    .span-12 { grid-column: span 12; }
    .span-6 { grid-column: span 6; }
    .span-4 { grid-column: span 4; }
    @media (max-width: 980px) {
      .span-6, .span-4 { grid-column: span 12; }
    }
    """

    html = f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Warehouse Optimization Portfolio Dashboard</title>
  <style>{css}</style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"title\">
      <h1>Warehouse Optimization and Robotics Operations Portfolio</h1>
      <p>Generated from Weeks 2-6 outputs. Timestamp: {html_escape(generated_at)}</p>
      <span class=\"pill\">Week 7 Portfolio Pack</span>
    </div>

    <div class=\"grid\">
      <div class=\"card span-12\">
        <h2>Executive Snapshot</h2>
        <div class=\"kpi\">
          <div class=\"box\"><div class=\"l\">Fleet Utilization (avg)</div><div class=\"v\">{format_metric(fleet_util, "%")}</div></div>
          <div class=\"box\"><div class=\"l\">Fleet Downtime (avg)</div><div class=\"v\">{format_metric(fleet_downtime, "%")}</div></div>
          <div class=\"box\"><div class=\"l\">Estimated Inventory Value</div><div class=\"v\">{format_metric(inv_value)}</div></div>
          <div class=\"box\"><div class=\"l\">Top Scenario Risk</div><div class=\"v\">{format_metric(top_risk_pct, "%")}</div></div>
        </div>
        <p class=\"muted\" style=\"margin-top: 10px;\">Top scenario by breach probability: <b>{html_escape(top_risk_name)}</b></p>
      </div>

      <div class=\"card span-6\">
        <h2>Week 2 - Pick Path Optimization</h2>
        {df_to_html_table(kpi_comp, max_rows=20)}
        {week2_images}
      </div>

      <div class=\"card span-6\">
        <h2>Week 3 - Slotting Optimization</h2>
        {df_to_html_table(slot_kpis, max_rows=20)}
        {image_block(image_paths["Slotting Impact Heatmap"], "Slotting impact heatmap", "Heatmap not found.")}
      </div>

      <div class=\"card span-6\">
        <h2>Week 4 - Control Tower</h2>
        {df_to_html_table(fleet_daily, max_rows=10)}
        {week4_images}
      </div>

      <div class=\"card span-6\">
        <h2>Week 5 - Audit Pack</h2>
        <p class=\"muted\">Inventory Accuracy</p>
        {df_to_html_table(inv_acc, max_rows=10)}
        <p class=\"muted\" style=\"margin-top: 10px;\">Exception SLA</p>
        {df_to_html_table(exc_sla, max_rows=20)}
        {link_block(evidence_index_local, "evidence_index.md")}
        {link_block(run_manifest_local, "run_manifest.json")}
      </div>

      <div class=\"card span-12\">
        <h2>Week 6 - Scenario Risk</h2>
        {df_to_html_table(scen_summary, max_rows=10)}
        <div class=\"grid\">
          <div class=\"card span-4\">{image_block(image_paths["SLA Breach Probability"], "SLA breach probability", "Chart not found.")}</div>
          <div class=\"card span-4\">{image_block(image_paths["Cycle Time P95"], "Cycle time p95")}</div>
          <div class=\"card span-4\">{image_block(image_paths["Throughput"], "Throughput")}</div>
        </div>
        {link_block(risk_report_local, "scenario_risk_report.md")}
        {link_block(ops_brief_local, "ops_brief.md")}
      </div>

      <div class=\"card span-12\">
        <h2>Run Commands</h2>
        <pre style=\"white-space: pre-wrap; margin: 0;\">python main.py
python src/portfolio/run_portfolio_pack.py</pre>
      </div>

      {missing_html}
    </div>
  </div>
</body>
</html>
"""

    return html, missing_inputs


def build_demo_script_md() -> str:
    return """# Demo Script (60-90 seconds)

## Goal
Show end-to-end warehouse operations thinking: optimization -> execution -> auditability -> risk.

## Recording flow
1. Open `output/portfolio/dashboard.html` and give a 1-sentence overview.
2. Week 2: show pick path KPI table and route charts.
3. Week 3: show slotting KPI table and delta heatmap.
4. Week 4: show utilization/fault charts and mention alerts + ops brief.
5. Week 5: open evidence links (`evidence_index.md`, `run_manifest.json`).
6. Week 6: show scenario risk table and SLA breach chart.

## Closing line
This portfolio demonstrates analytics and operations discipline that can be adapted to production WMS and WES data.
"""


def build_recruiter_one_pager_md() -> str:
    return """# Warehouse Optimization and Robotics Ops Portfolio

## Scope
This portfolio demonstrates: pick path optimization -> slotting strategy -> control tower KPIs -> audit-ready evidence -> scenario risk simulation.

## Delivered modules
- Week 2: pick path routing analysis and comparison KPIs.
- Week 3: ABC slotting and move-list impact analysis.
- Week 4: robotics fleet KPIs, alerts, and ops brief.
- Week 5: audit-ready inventory, cycle counts, exceptions, and run manifest.
- Week 6: Monte Carlo scenario risk with SLA breach probability.

## Primary artifacts
- Dashboard: `output/portfolio/dashboard.html`
- Evidence: `output/audit/evidence_index.md`, `output/audit/run_manifest.json`
- Risk report: `output/reports/scenario_risk_report.md`
- Ops brief: `output/reports/ops_brief.md`

## Next production steps
- Connect to real WMS order/inventory extracts.
- Stream robot telemetry and alert in near real time.
- Add tests and CI validation for deterministic output checks.
"""


def build_architecture_doc_md() -> str:
    return """# Architecture

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
"""


def main() -> None:
    ensure_dirs()

    dashboard_html, missing_inputs = build_dashboard()

    dashboard_path = PORTFOLIO_DIR / "dashboard.html"
    demo_path = PORTFOLIO_DIR / "demo_script.md"
    one_pager_path = PORTFOLIO_DIR / "recruiter_one_pager.md"
    architecture_path = DOCS_DIR / "architecture.md"

    write_text(dashboard_path, dashboard_html)
    write_text(demo_path, build_demo_script_md())
    write_text(one_pager_path, build_recruiter_one_pager_md())
    write_text(architecture_path, build_architecture_doc_md())

    print("DONE: portfolio pack generated")
    print(f" - {dashboard_path.relative_to(PROJECT_ROOT).as_posix()}")
    print(f" - {demo_path.relative_to(PROJECT_ROOT).as_posix()}")
    print(f" - {one_pager_path.relative_to(PROJECT_ROOT).as_posix()}")
    print(f" - {architecture_path.relative_to(PROJECT_ROOT).as_posix()}")

    if missing_inputs:
        print("WARN: Missing upstream artifacts (dashboard shows partial data):")
        for item in missing_inputs:
            print(f" - {item}")


if __name__ == "__main__":
    main()
