from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "output"
PORTFOLIO_DIR = OUTPUT_DIR / "portfolio"
ASSETS_DIR = PORTFOLIO_DIR / "assets"
DOCS_DIR = PROJECT_ROOT / "docs"
EST_TZ = timezone(timedelta(hours=-5), name="EST")

EXPECTED_FILES: dict[str, str] = {
    "Pick Path KPI Comparison": "output/reports/kpi_comparison.csv",
    "Pick Path Report (HTML)": "output/reports/pick_path_report.html",
    "Route Baseline": "output/charts/route_baseline.png",
    "Route Nearest Neighbor": "output/charts/route_nearest_neighbor.png",
    "Route Zone Batch": "output/charts/route_zone_batch.png",
    "ABC Summary": "output/reports/abc_summary.csv",
    "Move List Top 50": "output/reports/move_list_top50.csv",
    "Slotting KPIs": "output/reports/slotting_kpis.csv",
    "Slotting Heatmap Before": "output/charts/heatmap_slotting_before.png",
    "Slotting Heatmap After": "output/charts/heatmap_slotting_after.png",
    "Slotting Heatmap Delta": "output/charts/heatmap_slotting_delta.png",
    "Slotting Impact Heatmap (Combined)": "output/charts/heatmap_slotting_impact.png",
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

PORTFOLIO_VERSION = "2.1.0"

IMPACT_ASSUMPTIONS: dict[str, float] = {
    "orders_per_day": 1200.0,
    "working_days_per_year": 260.0,
    "baseline_pick_minutes_per_order": 3.5,
    "labor_cost_per_pick_min": 0.35,
    "baseline_downtime_pct": 14.0,
    "downtime_cost_per_pct_point_year": 12000.0,
    "implementation_cost_est": 125000.0,
}

CHANGELOG_ENTRIES: tuple[tuple[str, str], ...] = (
    ("2026-02-18", "Added business impact modeling and before/after summary tables."),
    ("2026-02-18", "Added assumptions/limits section plus version stamp and changelog panel."),
    ("2026-02-18", "Added centralized download center and chart image click-to-expand lightbox."),
)


def ensure_dirs() -> None:
    PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)


def project_path(relative_path: str) -> Path:
    return PROJECT_ROOT / relative_path


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_read_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None

    try:
        df = pd.read_csv(path)
    except Exception:
        df = None

    # Repair malformed CSVs where rows were emitted as a single quoted field.
    if df is None or (len(df.columns) == 1 and "," in str(df.columns[0])):
        try:
            raw = pd.read_csv(path, header=None, dtype=str).iloc[:, 0]
            split = raw.str.split(",", expand=True)
            header = [str(col).strip().strip('"') for col in split.iloc[0].tolist()]
            repaired = split.iloc[1:].copy()
            repaired.columns = header
            for col in repaired.columns:
                repaired[col] = repaired[col].astype(str).str.strip().str.strip('"')
            return repaired.reset_index(drop=True)
        except Exception:
            return df

    return df


def copy_asset(src: Path, out_name: str | None = None) -> str:
    if not src.exists():
        return ""

    dest_name = out_name or src.name
    dest = ASSETS_DIR / dest_name
    src_stat = src.stat()
    if dest.exists():
        dest_stat = dest.stat()
        if dest_stat.st_size == src_stat.st_size and int(dest_stat.st_mtime) >= int(src_stat.st_mtime):
            return dest.relative_to(PORTFOLIO_DIR).as_posix()

    shutil.copy2(src, dest)
    return dest.relative_to(PORTFOLIO_DIR).as_posix()


def first_numeric(df: pd.DataFrame | None, column: str) -> float | None:
    if df is None or df.empty or column not in df.columns:
        return None
    try:
        return float(pd.to_numeric(df[column], errors="coerce").dropna().iloc[0])
    except Exception:
        return None


def format_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.2f}%"


def format_currency(value: float | None) -> str:
    if value is None:
        return "-"
    return f"${value:,.0f}"


def format_number(value: float | None, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "-"
    return f"{value:,.{digits}f}{suffix}"


def format_signed(value: float | None, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:,.{digits}f}{suffix}"


def _normalize_column_name(name: object) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def find_column(df: pd.DataFrame | None, candidates: list[str]) -> str | None:
    if df is None or df.empty:
        return None
    normalized = {_normalize_column_name(col): str(col) for col in df.columns}
    for candidate in candidates:
        key = _normalize_column_name(candidate)
        if key in normalized:
            return normalized[key]
    return None


def mean_numeric(df: pd.DataFrame | None, candidates: list[str]) -> float | None:
    column_name = find_column(df, candidates)
    if column_name is None or df is None:
        return None
    series = pd.to_numeric(df[column_name], errors="coerce").dropna()
    if series.empty:
        return None
    return float(series.mean())


def scenario_value(
    scen_summary: pd.DataFrame | None,
    scenario_name: str,
    value_column_candidates: list[str],
) -> float | None:
    if scen_summary is None or scen_summary.empty:
        return None
    scenario_col = find_column(scen_summary, ["scenario"])
    value_col = find_column(scen_summary, value_column_candidates)
    if scenario_col is None or value_col is None:
        return None
    matched = scen_summary[
        scen_summary[scenario_col].astype(str).str.strip().str.upper() == scenario_name.strip().upper()
    ]
    if matched.empty:
        return None
    series = pd.to_numeric(matched[value_col], errors="coerce").dropna()
    if series.empty:
        return None
    return float(series.iloc[0])


def minimum_scenario(
    scen_summary: pd.DataFrame | None,
    value_column_candidates: list[str],
) -> tuple[str, float] | None:
    if scen_summary is None or scen_summary.empty:
        return None
    scenario_col = find_column(scen_summary, ["scenario"])
    value_col = find_column(scen_summary, value_column_candidates)
    if scenario_col is None or value_col is None:
        return None

    values = pd.to_numeric(scen_summary[value_col], errors="coerce")
    valid = scen_summary.assign(_value=values).dropna(subset=["_value"])
    if valid.empty:
        return None
    idx = valid["_value"].idxmin()
    row = valid.loc[idx]
    return str(row[scenario_col]), float(row["_value"])


def infer_baseline_scenario_name(
    scen_definitions: pd.DataFrame | None,
    scen_summary: pd.DataFrame | None,
) -> str | None:
    if scen_definitions is not None and not scen_definitions.empty:
        name_col = find_column(scen_definitions, ["name", "scenario"])
        demand_col = find_column(scen_definitions, ["demand_multiplier"])
        robots_col = find_column(scen_definitions, ["robots_available_pct"])
        fault_col = find_column(scen_definitions, ["fault_multiplier"])
        queue_col = find_column(scen_definitions, ["queue_delay_multiplier"])
        if (
            name_col is not None
            and demand_col is not None
            and robots_col is not None
            and fault_col is not None
            and queue_col is not None
        ):
            df = scen_definitions.copy()
            df["_demand"] = pd.to_numeric(df[demand_col], errors="coerce")
            df["_robots"] = pd.to_numeric(df[robots_col], errors="coerce")
            df["_fault"] = pd.to_numeric(df[fault_col], errors="coerce")
            df["_queue"] = pd.to_numeric(df[queue_col], errors="coerce")
            valid = df.dropna(subset=["_demand", "_robots", "_fault", "_queue"])
            if not valid.empty:
                baseline = valid[
                    (valid["_demand"].round(6) == 1.0)
                    & (valid["_robots"].round(6) == 1.0)
                    & (valid["_fault"].round(6) == 1.0)
                    & (valid["_queue"].round(6) == 1.0)
                ]
                if not baseline.empty:
                    return str(baseline.iloc[0][name_col])

    if scen_summary is not None and not scen_summary.empty:
        scenario_col = find_column(scen_summary, ["scenario"])
        if scenario_col is not None:
            names = scen_summary[scenario_col].astype(str).str.strip()
            upper = names.str.upper()
            for keyword in ("BASELINE", "NORMAL_OPERATIONS", "NORMAL", "STANDARD"):
                matches = names[upper.str.contains(keyword, na=False)]
                if not matches.empty:
                    return str(matches.iloc[0])
            return str(names.iloc[0])

    return None


def _format_table_cell(value: object) -> str:
    if pd.isna(value):
        return ""

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, int):
        return f"{value:,}"

    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        if abs(value) >= 100:
            return f"{value:,.2f}"
        return f"{value:.4f}".rstrip("0").rstrip(".")

    text = str(value).strip()
    if len(text) > 100:
        return f"{text[:97]}..."
    return text


def prettify_column_name(column_name: object) -> str:
    cleaned = str(column_name).strip().replace("_", " ").replace("-", " ")
    tokens = [token for token in cleaned.split() if token]
    if not tokens:
        return str(column_name)

    title_tokens: list[str] = []
    replacements = {
        "abc": "ABC",
        "avg": "Avg",
        "gt": "GT",
        "id": "ID",
        "ids": "IDs",
        "kpi": "KPI",
        "kpis": "KPIs",
        "lt": "LT",
        "p95": "P95",
        "pct": "Percent",
        "prob": "Probability",
        "qty": "Qty",
        "sku": "SKU",
        "sla": "SLA",
        "utc": "EST",
        "etc": "EST",
        "wes": "WES",
        "wms": "WMS",
    }

    for token in tokens:
        lower = token.lower()
        if lower in replacements:
            title_tokens.append(replacements[lower])
        elif token.isupper() and len(token) <= 4:
            title_tokens.append(token)
        elif token.isdigit():
            title_tokens.append(token)
        else:
            title_tokens.append(token.capitalize())

    title_text = " ".join(title_tokens)
    title_text = title_text.replace(" Percent", " %")
    title_text = title_text.replace("Snapshot Est", "Snapshot EST")
    title_text = title_text.replace("Timestamp Est", "Timestamp EST")
    return title_text


def df_to_html_table(df: pd.DataFrame | None, max_rows: int = 25) -> str:
    if df is None or df.empty:
        return "<p class='muted'>No data found.</p>"

    preview = df.head(max_rows).copy()
    preview.columns = [prettify_column_name(col) for col in preview.columns]
    for col in preview.columns:
        preview[col] = preview[col].map(_format_table_cell)

    table_html = preview.to_html(index=False, classes="table", border=0, escape=True)
    return f"<div class='table-wrap'>{table_html}</div>"


def image_tile(src: str, alt: str, caption: str, missing_note: str = "Image not available.") -> str:
    if src:
        media_html = (
            f"<img src=\"{src}\" alt=\"{escape(alt)}\" loading=\"lazy\" "
            f"class=\"expandable-img\" data-caption=\"{escape(caption)}\"/>"
        )
    else:
        media_html = f"<div class=\"viz-empty\">{escape(missing_note)}</div>"

    return f"""
    <figure class="viz-card">
      {media_html}
      <figcaption>{escape(caption)}</figcaption>
    </figure>
    """


def link_block(src: str, label: str) -> str:
    if not src:
        return ""
    return f"<a class=\"doc-link\" href=\"{src}\">{escape(label)}</a>"


def link_row(items: list[tuple[str, str]]) -> str:
    links = [link_block(path, label) for path, label in items if path]
    if not links:
        return "<p class='muted'>No linked artifacts available.</p>"
    return "<div class=\"doc-links\">" + "".join(links) + "</div>"


def build_before_after_row(
    area: str,
    before: float | None,
    after: float | None,
    unit: str = "",
    source: str = "",
) -> dict[str, str]:
    delta = None
    delta_pct = None
    if before is not None and after is not None:
        delta = before - after
        if before != 0:
            delta_pct = (delta / abs(before)) * 100.0

    return {
        "Area": area,
        "Before": format_number(before, suffix=unit),
        "After": format_number(after, suffix=unit),
        "Gain": format_signed(delta, suffix=unit),
        "Gain %": format_signed(delta_pct, suffix="%"),
        "Source": source or "-",
    }


def build_download_groups_html(groups: dict[str, list[tuple[str, str]]]) -> str:
    cards: list[str] = []
    ordered_groups = ("Reports", "Charts", "Documents")
    for group_name in ordered_groups:
        items = groups.get(group_name, [])
        if not items:
            continue
        list_items = "".join(
            f"<li><a href=\"{path}\" download>{escape(label)}</a><span>{escape(path)}</span></li>"
            for label, path in sorted(items, key=lambda item: item[0].lower())
        )
        cards.append(
            f"""
            <div class="download-card">
              <h3>{escape(group_name)}</h3>
              <ul class="download-list">{list_items}</ul>
            </div>
            """
        )

    if not cards:
        return "<p class='muted'>No files are currently available for download.</p>"
    return "<div class=\"download-grid\">" + "".join(cards) + "</div>"


def build_dashboard() -> tuple[str, list[str]]:
    generated_at = datetime.now(EST_TZ).strftime("%Y-%m-%d %H:%M EST")

    kpi_comp = safe_read_csv(project_path(EXPECTED_FILES["Pick Path KPI Comparison"]))
    slot_kpis = safe_read_csv(project_path(EXPECTED_FILES["Slotting KPIs"]))
    fleet_daily = safe_read_csv(project_path(EXPECTED_FILES["Fleet KPIs Daily"]))
    inv_acc = safe_read_csv(project_path(EXPECTED_FILES["Inventory Accuracy"]))
    exc_sla = safe_read_csv(project_path(EXPECTED_FILES["Exception SLA"]))
    scen_definitions = safe_read_csv(project_path(EXPECTED_FILES["Scenario Definitions"]))
    scen_summary = safe_read_csv(project_path(EXPECTED_FILES["Scenario Summary"]))

    asset_paths = {label: copy_asset(project_path(rel_path)) for label, rel_path in EXPECTED_FILES.items()}

    image_keys = (
        "Route Baseline",
        "Route Nearest Neighbor",
        "Route Zone Batch",
        "Slotting Heatmap Before",
        "Slotting Heatmap After",
        "Slotting Heatmap Delta",
        "Slotting Impact Heatmap (Combined)",
        "Utilization Chart",
        "Faults Chart",
        "SLA Breach Probability",
        "Cycle Time P95",
        "Throughput",
    )
    image_paths = {key: asset_paths.get(key, "") for key in image_keys}

    evidence_index_local = asset_paths.get("Evidence Index", "")
    run_manifest_local = asset_paths.get("Run Manifest", "")
    ops_brief_local = asset_paths.get("Ops Brief", "")
    risk_report_local = asset_paths.get("Scenario Risk Report", "")
    pick_path_report_local = asset_paths.get("Pick Path Report (HTML)", "")
    project_changelog_local = copy_asset(PROJECT_ROOT / "artifacts" / "project" / "changelog.md", "project_changelog.md")
    architecture_local = copy_asset(DOCS_DIR / "architecture.md", "architecture.md")

    fleet_util = mean_numeric(fleet_daily, ["utilization_pct"])
    fleet_downtime = mean_numeric(fleet_daily, ["downtime_pct"])
    inv_value = first_numeric(inv_acc, "total_inventory_value_est")

    top_risk_pct: float | None = None
    top_risk_name = "n/a"
    risk_col = find_column(scen_summary, ["prob_sla_breach_gt_threshold_pct"])
    scenario_col = find_column(scen_summary, ["scenario"])
    if scen_summary is not None and not scen_summary.empty and risk_col is not None:
        risk_series = pd.to_numeric(scen_summary[risk_col], errors="coerce")
        valid = scen_summary.assign(_risk=risk_series).dropna(subset=["_risk"])
        if not valid.empty:
            idx = valid["_risk"].idxmax()
            top_row = valid.loc[idx]
            top_risk_pct = float(top_row["_risk"])
            if scenario_col is not None:
                top_risk_name = str(top_row[scenario_col])

    pick_before = mean_numeric(kpi_comp, ["distance_baseline_random"])
    pick_after = mean_numeric(kpi_comp, ["best_distance"])
    pick_improvement_pct = mean_numeric(kpi_comp, ["pct_improvement_vs_baseline"])
    if pick_improvement_pct is None and pick_before not in (None, 0.0) and pick_after is not None:
        pick_improvement_pct = ((pick_before - pick_after) / pick_before) * 100.0

    slot_before = mean_numeric(slot_kpis, ["avg_distance_before"])
    slot_after = mean_numeric(slot_kpis, ["avg_distance_after"])
    slot_improvement_pct = mean_numeric(slot_kpis, ["pct_improvement"])
    if slot_improvement_pct is None and slot_before not in (None, 0.0) and slot_after is not None:
        slot_improvement_pct = ((slot_before - slot_after) / slot_before) * 100.0

    baseline_scenario_name = infer_baseline_scenario_name(scen_definitions, scen_summary)
    scenario_baseline_sla = (
        scenario_value(scen_summary, baseline_scenario_name, ["avg_sla_breach_pct"])
        if baseline_scenario_name
        else None
    )
    best_scenario = minimum_scenario(scen_summary, ["avg_sla_breach_pct"])
    best_scenario_name = best_scenario[0] if best_scenario else "n/a"
    best_scenario_sla = best_scenario[1] if best_scenario else None

    before_after_df = pd.DataFrame(
        [
            build_before_after_row(
                "Week 2 Pick Path - Avg Distance",
                pick_before,
                pick_after,
                unit=" m",
                source="kpi_comparison.csv",
            ),
            build_before_after_row(
                "Week 3 Slotting - Avg Distance",
                slot_before,
                slot_after,
                unit=" m",
                source="slotting_kpis.csv",
            ),
            build_before_after_row(
                "Week 4 Fleet Downtime",
                IMPACT_ASSUMPTIONS["baseline_downtime_pct"],
                fleet_downtime,
                unit="%",
                source="fleet_daily_kpis.csv + assumption baseline",
            ),
            build_before_after_row(
                "Week 6 SLA Breach Risk",
                scenario_baseline_sla,
                best_scenario_sla,
                unit="%",
                source=(
                    f"scenario_summary.csv (baseline: {baseline_scenario_name or 'n/a'}, best: {best_scenario_name})"
                ),
            ),
        ]
    )

    improvement_components = [value for value in (pick_improvement_pct, slot_improvement_pct) if value is not None]
    blended_improvement_pct = (
        float(sum(improvement_components) / len(improvement_components)) if improvement_components else None
    )

    annual_orders = IMPACT_ASSUMPTIONS["orders_per_day"] * IMPACT_ASSUMPTIONS["working_days_per_year"]
    annual_minutes_saved = (
        annual_orders
        * IMPACT_ASSUMPTIONS["baseline_pick_minutes_per_order"]
        * (blended_improvement_pct / 100.0)
        if blended_improvement_pct is not None
        else None
    )
    annual_labor_savings = (
        annual_minutes_saved * IMPACT_ASSUMPTIONS["labor_cost_per_pick_min"] if annual_minutes_saved is not None else None
    )
    downtime_reduction_pct = (
        max(0.0, IMPACT_ASSUMPTIONS["baseline_downtime_pct"] - fleet_downtime) if fleet_downtime is not None else None
    )
    annual_downtime_savings = (
        downtime_reduction_pct * IMPACT_ASSUMPTIONS["downtime_cost_per_pct_point_year"]
        if downtime_reduction_pct is not None
        else None
    )

    annual_impact_components = [value for value in (annual_labor_savings, annual_downtime_savings) if value is not None]
    total_annual_impact = float(sum(annual_impact_components)) if annual_impact_components else None
    payback_months = (
        (IMPACT_ASSUMPTIONS["implementation_cost_est"] / total_annual_impact) * 12.0
        if total_annual_impact not in (None, 0.0)
        else None
    )
    roi_pct = (
        ((total_annual_impact - IMPACT_ASSUMPTIONS["implementation_cost_est"]) / IMPACT_ASSUMPTIONS["implementation_cost_est"])
        * 100.0
        if total_annual_impact is not None
        else None
    )

    available_asset_count = sum(1 for path in asset_paths.values() if path)
    version_stamp = f"{PORTFOLIO_VERSION} | artifacts available: {available_asset_count}/{len(EXPECTED_FILES)}"

    missing_inputs = [f"{label}: {rel_path}" for label, rel_path in EXPECTED_FILES.items() if not project_path(rel_path).exists()]

    missing_html = ""
    if missing_inputs:
        missing_items = "".join(f"<li><code>{escape(item)}</code></li>" for item in missing_inputs)
        missing_html = f"""
        <section class="warning" aria-label="Missing inputs">
          <h2>Missing Inputs</h2>
          <p>The dashboard loaded with partial data. Run the upstream pipeline steps to fill missing artifacts:</p>
          <ul>{missing_items}</ul>
        </section>
        """

    assumptions_items = [
        f"Orders/day assumed: {int(IMPACT_ASSUMPTIONS['orders_per_day']):,}",
        f"Working days/year assumed: {int(IMPACT_ASSUMPTIONS['working_days_per_year']):,}",
        f"Baseline pick minutes/order: {IMPACT_ASSUMPTIONS['baseline_pick_minutes_per_order']:.2f}",
        f"Labor cost per pick minute: ${IMPACT_ASSUMPTIONS['labor_cost_per_pick_min']:.2f}",
        f"Baseline downtime used for comparison: {IMPACT_ASSUMPTIONS['baseline_downtime_pct']:.2f}%",
        f"Implementation cost estimate: ${IMPACT_ASSUMPTIONS['implementation_cost_est']:,.0f}",
    ]
    assumptions_html = "".join(f"<li>{escape(item)}</li>" for item in assumptions_items)

    limits_items = [
        "Business impact values are directional estimates based on simulated outputs.",
        "No labor scheduling, overtime, equipment depreciation, or tax effects are included.",
        "Before vs after comparisons rely on available CSV artifacts for the current run only.",
        "If any upstream files are missing, related calculations show partial or blank values.",
    ]
    limits_html = "".join(f"<li>{escape(item)}</li>" for item in limits_items)

    changelog_items_html = "".join(
        f"<li><span>{escape(date)}</span><p>{escape(change)}</p></li>" for date, change in CHANGELOG_ENTRIES
    )

    download_groups: dict[str, list[tuple[str, str]]] = {"Reports": [], "Charts": [], "Documents": []}
    for label, rel_path in EXPECTED_FILES.items():
        asset_rel_path = asset_paths.get(label, "")
        if not asset_rel_path:
            continue
        suffix = Path(rel_path).suffix.lower()
        if suffix == ".csv":
            download_groups["Reports"].append((label, asset_rel_path))
        elif suffix in {".png", ".jpg", ".jpeg", ".svg"}:
            download_groups["Charts"].append((label, asset_rel_path))
        else:
            download_groups["Documents"].append((label, asset_rel_path))

    download_groups["Documents"].extend(
        [
            ("Dashboard HTML", "dashboard.html"),
            ("Credits and Help", "credits.html"),
            ("Demo Script", "demo_script.md"),
            ("Recruiter One Pager", "recruiter_one_pager.md"),
        ]
    )
    if architecture_local:
        download_groups["Documents"].append(("Architecture", architecture_local))
    if project_changelog_local:
        download_groups["Documents"].append(("Project Changelog", project_changelog_local))

    download_center_html = build_download_groups_html(download_groups)

    css = """
    :root {
      --bg: #0b0f14;
      --surface: #111823;
      --surface-soft: #0d1420;
      --line: #1f2a37;
      --line-strong: #2d3f51;
      --text: #e6eaf2;
      --muted: #98a2b3;
      --accent: #7dd3fc;
      --accent-soft: rgba(125, 211, 252, 0.12);
      --warning-bg: #2a2214;
      --warning-line: #8a6c3d;
      --shadow: 0 12px 28px rgba(0, 0, 0, 0.35);
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      font-family: "Trebuchet MS", "Lucida Sans Unicode", "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 8% 0%, #122433 0%, transparent 40%),
        radial-gradient(circle at 100% 0%, #123024 0%, transparent 30%),
        var(--bg);
      line-height: 1.45;
    }
    .wrap {
      max-width: 1240px;
      margin: 0 auto;
      padding: 24px 16px 42px;
    }
    .hero {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 18px;
      background: linear-gradient(130deg, #121b27 0%, #0f1a26 52%, #101d18 100%);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 22px;
      box-shadow: var(--shadow);
    }
    .hero h1 {
      margin: 0;
      font-size: 30px;
      line-height: 1.2;
      letter-spacing: 0.2px;
    }
    .hero p {
      margin: 10px 0 0;
      color: var(--muted);
      max-width: 80ch;
    }
    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
    }
    .chip {
      display: inline-block;
      padding: 6px 10px;
      border: 1px solid var(--line-strong);
      border-radius: 999px;
      background: var(--surface);
      font-size: 12px;
      color: var(--muted);
    }
    .chip.accent {
      color: var(--accent);
      border-color: rgba(125, 211, 252, 0.35);
      background: var(--accent-soft);
    }
    .jump {
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(13, 20, 32, 0.8);
      padding: 12px;
      align-self: start;
    }
    .jump h2 {
      margin: 0 0 8px;
      font-size: 14px;
    }
    .jump a {
      display: block;
      padding: 5px 0;
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
      font-size: 13px;
    }
    .jump a:hover {
      text-decoration: underline;
    }
    .warning {
      margin-top: 14px;
      border: 1px solid var(--warning-line);
      border-radius: 14px;
      background: var(--warning-bg);
      padding: 14px 16px;
    }
    .warning h2 {
      margin: 0;
      font-size: 18px;
    }
    .warning p {
      margin: 8px 0 0;
      color: #dcc29b;
    }
    .warning ul {
      margin: 10px 0 0;
      padding-left: 18px;
    }
    .panel {
      margin-top: 14px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
      box-shadow: var(--shadow);
      scroll-margin-top: 12px;
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }
    .panel h2 {
      margin: 0;
      font-size: 20px;
    }
    .panel-note {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
    }
    .kpi-grid {
      margin-top: 10px;
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
    .kpi {
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--surface-soft);
      padding: 10px;
    }
    .kpi .label {
      font-size: 12px;
      color: var(--muted);
      letter-spacing: 0.2px;
    }
    .kpi .value {
      margin-top: 5px;
      font-size: 25px;
      font-weight: 700;
      line-height: 1.05;
    }
    .impact-grid {
      margin-top: 10px;
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(5, minmax(0, 1fr));
    }
    .impact-kpi {
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--surface-soft);
      padding: 10px;
    }
    .impact-kpi .label {
      font-size: 12px;
      color: var(--muted);
      letter-spacing: 0.2px;
    }
    .impact-kpi .value {
      margin-top: 5px;
      font-size: 21px;
      font-weight: 700;
      line-height: 1.1;
    }
    .stamp {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }
    .stamp .item {
      padding: 5px 9px;
      border-radius: 999px;
      border: 1px solid var(--line-strong);
      background: #0f1a26;
      color: #b7c8d9;
      font-size: 12px;
      white-space: nowrap;
    }
    .inline-list {
      margin: 8px 0 0;
      padding-left: 18px;
    }
    .inline-list li {
      margin: 6px 0;
      color: #cbd8e6;
    }
    .changelog {
      margin-top: 8px;
      padding-left: 0;
      list-style: none;
    }
    .changelog li {
      margin: 0 0 8px;
      padding: 9px 10px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #0f1724;
    }
    .changelog li span {
      display: inline-block;
      font-size: 11px;
      letter-spacing: 0.2px;
      color: #8fb8d2;
      margin-bottom: 4px;
      font-weight: 700;
    }
    .changelog li p {
      margin: 0;
      color: #d6e3f1;
      font-size: 13px;
    }
    .download-grid {
      margin-top: 10px;
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .download-card {
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--surface-soft);
      padding: 10px;
      min-width: 0;
    }
    .download-card h3 {
      margin: 0;
      font-size: 14px;
    }
    .download-list {
      margin: 8px 0 0;
      padding-left: 18px;
    }
    .download-list li {
      margin: 6px 0;
    }
    .download-list a {
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }
    .download-list a:hover {
      text-decoration: underline;
    }
    .download-list span {
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 11px;
      word-break: break-all;
    }
    .muted {
      color: var(--muted);
      margin: 10px 0 0;
    }
    .table-wrap {
      margin-top: 8px;
      width: 100%;
      max-height: 430px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #0b0f14;
    }
    .table {
      width: 100%;
      min-width: 560px;
      border-collapse: separate;
      border-spacing: 0;
      font-size: 12px;
    }
    .table th,
    .table td {
      padding: 8px 10px;
      border-bottom: 1px solid #1b2735;
      text-align: left;
      white-space: nowrap;
      vertical-align: top;
    }
    .table th {
      position: sticky;
      top: 0;
      z-index: 2;
      background: #121b27;
      color: #d8edf8;
    }
    .table tr:nth-child(even) td {
      background: #0f1724;
    }
    .viz-grid {
      display: grid;
      gap: 10px;
      margin-top: 10px;
    }
    .viz-grid.v3 {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .viz-grid.v2 {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .viz-card {
      margin: 0;
      border: 1px solid var(--line);
      border-radius: 12px;
      overflow: hidden;
      background: var(--surface-soft);
    }
    .viz-card img {
      display: block;
      width: 100%;
      height: 250px;
      object-fit: contain;
      background: #0b0f14;
      border-bottom: 1px solid var(--line);
      cursor: zoom-in;
      transition: transform 140ms ease, filter 140ms ease;
    }
    .viz-card img:hover {
      transform: scale(1.01);
      filter: brightness(1.04);
    }
    .viz-card img:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: -2px;
    }
    .viz-card figcaption {
      padding: 8px 10px;
      color: #afbac9;
      font-size: 12px;
    }
    .viz-empty {
      min-height: 170px;
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: 10px;
      color: var(--muted);
      background: #0b0f14;
      border-bottom: 1px solid var(--line);
      font-size: 12px;
    }
    .split {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .split h3 {
      margin: 0;
      font-size: 15px;
    }
    .doc-links {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }
    .doc-link {
      display: inline-block;
      padding: 7px 10px;
      border: 1px solid #2f5160;
      border-radius: 10px;
      background: #0f1a26;
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
      font-size: 12px;
    }
    .doc-link:hover {
      text-decoration: underline;
    }
    pre {
      margin: 8px 0 0;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #0b0f14;
      padding: 10px 12px;
      font-size: 13px;
      overflow-x: auto;
    }
    code {
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
    }
    .mt-10 {
      margin-top: 10px;
    }
    .footer-note {
      margin-top: 14px;
      color: var(--muted);
      font-size: 12px;
    }
    .lightbox {
      position: fixed;
      inset: 0;
      z-index: 1200;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 22px;
      background: rgba(3, 6, 10, 0.86);
    }
    .lightbox.open {
      display: flex;
    }
    .lightbox-dialog {
      position: relative;
      max-width: min(96vw, 1500px);
      max-height: 94vh;
      border: 1px solid var(--line-strong);
      border-radius: 14px;
      background: #0c1119;
      overflow: hidden;
      box-shadow: 0 20px 52px rgba(0, 0, 0, 0.55);
    }
    .lightbox img {
      display: block;
      width: 100%;
      max-width: min(96vw, 1450px);
      max-height: calc(94vh - 56px);
      object-fit: contain;
      background: #060a0f;
    }
    .lightbox-caption {
      padding: 9px 12px;
      border-top: 1px solid var(--line);
      color: #c5d3e1;
      font-size: 12px;
      background: #0f1724;
    }
    .lightbox-close {
      position: absolute;
      top: 8px;
      right: 8px;
      border: 1px solid #345064;
      border-radius: 9px;
      background: rgba(11, 16, 24, 0.94);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
      padding: 5px 9px;
      cursor: pointer;
    }
    .lightbox-close:hover {
      background: rgba(17, 29, 45, 0.96);
    }
    .no-scroll {
      overflow: hidden;
    }
    @media (max-width: 1080px) {
      .hero {
        grid-template-columns: 1fr;
      }
      .kpi-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .impact-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
      .download-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .viz-grid.v3 {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
    @media (max-width: 760px) {
      .wrap {
        padding: 16px 10px 28px;
      }
      .hero h1 {
        font-size: 24px;
      }
      .panel {
        padding: 12px;
      }
      .kpi-grid {
        grid-template-columns: 1fr;
      }
      .impact-grid,
      .download-grid {
        grid-template-columns: 1fr;
      }
      .split,
      .viz-grid.v3,
      .viz-grid.v2 {
        grid-template-columns: 1fr;
      }
      .table {
        min-width: 460px;
      }
      .viz-card img {
        height: 220px;
      }
      .lightbox {
        padding: 8px;
      }
      .lightbox-dialog {
        border-radius: 10px;
      }
      .lightbox img {
        max-height: calc(96vh - 52px);
      }
    }
    """

    lightbox_html = """
    <div class="lightbox" id="image-lightbox" aria-hidden="true">
      <div class="lightbox-dialog" role="dialog" aria-modal="true" aria-label="Expanded chart image">
        <button type="button" class="lightbox-close" id="image-lightbox-close">Close</button>
        <img id="image-lightbox-img" alt="" />
        <div class="lightbox-caption" id="image-lightbox-caption"></div>
      </div>
    </div>
    <script>
      (function() {
        const lightbox = document.getElementById("image-lightbox");
        const lightboxImg = document.getElementById("image-lightbox-img");
        const lightboxCaption = document.getElementById("image-lightbox-caption");
        const closeButton = document.getElementById("image-lightbox-close");
        if (!lightbox || !lightboxImg || !lightboxCaption || !closeButton) {
          return;
        }

        function closeLightbox() {
          lightbox.classList.remove("open");
          lightbox.setAttribute("aria-hidden", "true");
          document.body.classList.remove("no-scroll");
          lightboxImg.removeAttribute("src");
          lightboxImg.alt = "";
          lightboxCaption.textContent = "";
        }

        function openLightbox(source, altText, caption) {
          if (!source) {
            return;
          }
          lightboxImg.src = source;
          lightboxImg.alt = altText || caption || "Expanded chart image";
          lightboxCaption.textContent = caption || altText || "";
          lightbox.classList.add("open");
          lightbox.setAttribute("aria-hidden", "false");
          document.body.classList.add("no-scroll");
        }

        document.querySelectorAll(".expandable-img").forEach((img) => {
          img.setAttribute("role", "button");
          img.setAttribute("tabindex", "0");
          img.setAttribute("title", "Click to expand");

          img.addEventListener("click", () => {
            openLightbox(img.getAttribute("src"), img.getAttribute("alt"), img.dataset.caption || "");
          });

          img.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              openLightbox(img.getAttribute("src"), img.getAttribute("alt"), img.dataset.caption || "");
            }
          });
        });

        closeButton.addEventListener("click", closeLightbox);
        lightbox.addEventListener("click", (event) => {
          if (event.target === lightbox) {
            closeLightbox();
          }
        });
        document.addEventListener("keydown", (event) => {
          if (event.key === "Escape" && lightbox.classList.contains("open")) {
            closeLightbox();
          }
        });
      })();
    </script>
    """

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Warehouse Optimization Portfolio Dashboard</title>
  <style>{css}</style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <div>
        <h1>Warehouse Optimization and Robotics Operations Portfolio</h1>
        <p>Consolidated operations view across Weeks 2-6, including audit evidence and scenario risk outputs.</p>
        <div class="chips">
          <span class="chip accent">Week 7 Portfolio Pack</span>
          <span class="chip">Generated: {escape(generated_at)}</span>
          <span class="chip">Version: {escape(version_stamp)}</span>
        </div>
      </div>
      <nav class="jump" aria-label="Quick jump">
        <h2>Quick Jump</h2>
        <a href="#executive">Executive Snapshot</a>
        <a href="#impact">Business Impact</a>
        <a href="#before-after">Before vs After</a>
        <a href="#assumptions">Assumptions and Limits</a>
        <a href="#changelog">Change Log and Version</a>
        <a href="#week2">Week 2 Pick Path</a>
        <a href="#week3">Week 3 Slotting</a>
        <a href="#week4">Week 4 Operations</a>
        <a href="#week5">Week 5 Audit Pack</a>
        <a href="#week6">Week 6 Scenario Risk</a>
        <a href="#downloads">Download Center</a>
        <a href="#artifacts">Run and Artifacts</a>
        <a href="credits.html">Credits and Help</a>
      </nav>
    </header>

    {missing_html}

    <section id="executive" class="panel">
      <div class="panel-head">
        <h2>Executive Snapshot</h2>
        <p class="panel-note">Key indicators pulled from current report outputs.</p>
      </div>
      <div class="kpi-grid">
        <div class="kpi"><div class="label">Fleet Utilization (avg)</div><div class="value">{format_percent(fleet_util)}</div></div>
        <div class="kpi"><div class="label">Fleet Downtime (avg)</div><div class="value">{format_percent(fleet_downtime)}</div></div>
        <div class="kpi"><div class="label">Estimated Inventory Value</div><div class="value">{format_currency(inv_value)}</div></div>
        <div class="kpi"><div class="label">Top Scenario Risk</div><div class="value">{format_percent(top_risk_pct)}</div></div>
      </div>
      <p class="muted">Top scenario by breach probability: <b>{escape(top_risk_name)}</b></p>
    </section>

    <section id="impact" class="panel">
      <div class="panel-head">
        <h2>Business Impact Panel</h2>
        <p class="panel-note">Directional financial impact estimate using current portfolio metrics.</p>
      </div>
      <div class="impact-grid">
        <div class="impact-kpi"><div class="label">Travel Improvement (blended)</div><div class="value">{format_percent(blended_improvement_pct)}</div></div>
        <div class="impact-kpi"><div class="label">Labor Minutes Saved / Year</div><div class="value">{format_number(annual_minutes_saved, 0)}</div></div>
        <div class="impact-kpi"><div class="label">Estimated Labor Savings / Year</div><div class="value">{format_currency(annual_labor_savings)}</div></div>
        <div class="impact-kpi"><div class="label">Downtime Savings / Year</div><div class="value">{format_currency(annual_downtime_savings)}</div></div>
        <div class="impact-kpi"><div class="label">Total Annual Impact</div><div class="value">{format_currency(total_annual_impact)}</div></div>
      </div>
      <div class="impact-grid">
        <div class="impact-kpi"><div class="label">Payback Period</div><div class="value">{format_number(payback_months, 1, " mo")}</div></div>
        <div class="impact-kpi"><div class="label">Estimated ROI</div><div class="value">{format_percent(roi_pct)}</div></div>
        <div class="impact-kpi"><div class="label">Implementation Cost (assumed)</div><div class="value">{format_currency(IMPACT_ASSUMPTIONS["implementation_cost_est"])}</div></div>
      </div>
      <p class="muted">Model combines Week 2 and Week 3 travel reductions with Week 4 downtime delta vs assumed baseline.</p>
    </section>

    <section id="before-after" class="panel">
      <div class="panel-head">
        <h2>Before vs After Summary Card</h2>
        <p class="panel-note">Positive gain indicates improvement (before minus after).</p>
      </div>
      {df_to_html_table(before_after_df, max_rows=10)}
    </section>

    <section id="assumptions" class="panel">
      <div class="panel-head">
        <h2>Assumptions and Limits</h2>
        <p class="panel-note">Context to interpret calculations and comparisons.</p>
      </div>
      <div class="split">
        <div>
          <h3>Assumptions</h3>
          <ul class="inline-list">{assumptions_html}</ul>
        </div>
        <div>
          <h3>Limits</h3>
          <ul class="inline-list">{limits_html}</ul>
        </div>
      </div>
    </section>

    <section id="changelog" class="panel">
      <div class="panel-head">
        <h2>Change Log and Version Stamp</h2>
        <p class="panel-note">Recent portfolio updates and current build metadata.</p>
      </div>
      <div class="stamp">
        <span class="item">Version: {escape(PORTFOLIO_VERSION)}</span>
        <span class="item">Generated: {escape(generated_at)}</span>
        <span class="item">Assets Ready: {available_asset_count}/{len(EXPECTED_FILES)}</span>
      </div>
      <ul class="changelog">{changelog_items_html}</ul>
      {link_row([
        (project_changelog_local, "project_changelog.md"),
        (run_manifest_local, "run_manifest.json"),
      ])}
    </section>

    <section id="week2" class="panel">
      <div class="panel-head">
        <h2>Week 2 - Pick Path Optimization</h2>
        <p class="panel-note">Route performance comparison and visual route snapshots.</p>
      </div>
      {df_to_html_table(kpi_comp, max_rows=20)}
      <div class="viz-grid v3">
        {image_tile(image_paths["Route Baseline"], "Route baseline", "Baseline route")}
        {image_tile(image_paths["Route Nearest Neighbor"], "Route nearest neighbor", "Nearest-neighbor route")}
        {image_tile(image_paths["Route Zone Batch"], "Route zone batch", "Zone-batch route")}
      </div>
      {link_row([(pick_path_report_local, "pick_path_report.html")])}
    </section>

    <section id="week3" class="panel">
      <div class="panel-head">
        <h2>Week 3 - Slotting Optimization</h2>
        <p class="panel-note">Slotting KPI summary with separate before, after, and delta heatmaps.</p>
      </div>
      {df_to_html_table(slot_kpis, max_rows=20)}
      <div class="viz-grid v3">
        {image_tile(image_paths["Slotting Heatmap Before"], "Slotting heatmap before", "Before heatmap", "Before heatmap not found.")}
        {image_tile(image_paths["Slotting Heatmap After"], "Slotting heatmap after", "After heatmap", "After heatmap not found.")}
        {image_tile(image_paths["Slotting Heatmap Delta"], "Slotting heatmap delta", "Delta heatmap (After - Before)", "Delta heatmap not found.")}
      </div>
      {link_row([(image_paths["Slotting Impact Heatmap (Combined)"], "slotting_heatmap_combined.png")])}
    </section>

    <section id="week4" class="panel">
      <div class="panel-head">
        <h2>Week 4 - Operations</h2>
        <p class="panel-note">Daily fleet KPIs with utilization and fault trends.</p>
      </div>
      {df_to_html_table(fleet_daily, max_rows=12)}
      <div class="viz-grid v2">
        {image_tile(image_paths["Utilization Chart"], "Utilization over time", "Fleet utilization trend", "Utilization chart not found.")}
        {image_tile(image_paths["Faults Chart"], "Faults over time", "Fleet faults trend", "Fault chart not found.")}
      </div>
    </section>

    <section id="week5" class="panel">
      <div class="panel-head">
        <h2>Week 5 - Audit Pack</h2>
        <p class="panel-note">Inventory controls, cycle count outcomes, and exception SLA coverage.</p>
      </div>
      <div class="split">
        <div>
          <h3>Inventory Accuracy</h3>
          {df_to_html_table(inv_acc, max_rows=10)}
        </div>
        <div>
          <h3>Exception SLA</h3>
          {df_to_html_table(exc_sla, max_rows=20)}
        </div>
      </div>
      {link_row([(evidence_index_local, "evidence_index.md"), (run_manifest_local, "run_manifest.json")])}
    </section>

    <section id="week6" class="panel">
      <div class="panel-head">
        <h2>Week 6 - Scenario Risk</h2>
        <p class="panel-note">SLA breach exposure and cycle-time/throughput tradeoff across scenarios.</p>
      </div>
      {df_to_html_table(scen_summary, max_rows=12)}
      <div class="viz-grid v3">
        {image_tile(image_paths["SLA Breach Probability"], "SLA breach probability", "SLA breach probability")}
        {image_tile(image_paths["Cycle Time P95"], "Cycle time p95 by scenario", "Cycle time p95")}
        {image_tile(image_paths["Throughput"], "Throughput by scenario", "Throughput by scenario")}
      </div>
      {link_row([(risk_report_local, "scenario_risk_report.md"), (ops_brief_local, "ops_brief.md")])}
    </section>

    <section id="artifacts" class="panel">
      <div class="panel-head">
        <h2>Run and Artifacts</h2>
        <p class="panel-note">Entry commands and linked outputs for review.</p>
      </div>
      <div class="split">
        <div>
          <h3>Run Commands</h3>
          <pre><code>python main.py
python src/portfolio/portfolio.py</code></pre>
        </div>
        <div>
          <h3>Primary Artifacts</h3>
          {link_row([
            (evidence_index_local, "evidence_index.md"),
            (run_manifest_local, "run_manifest.json"),
            (risk_report_local, "scenario_risk_report.md"),
            (ops_brief_local, "ops_brief.md"),
            (project_changelog_local, "project_changelog.md"),
            (architecture_local, "architecture.md"),
            ("credits.html", "credits.html"),
          ])}
        </div>
      </div>
      <p class="footer-note">Tip: run <code>python main.py</code> first for a full refresh, then regenerate this dashboard.</p>
    </section>

    <section id="downloads" class="panel">
      <div class="panel-head">
        <h2>Download Center</h2>
        <p class="panel-note">One-click access to available reports, charts, and documentation.</p>
      </div>
      {download_center_html}
    </section>
  </div>
  {lightbox_html}
</body>
</html>
"""

    return html, missing_inputs


def build_credits_page_html() -> str:
    generated_at = datetime.now(EST_TZ).strftime("%Y-%m-%d %H:%M EST")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Portfolio Credits and Help</title>
  <style>
    :root {{
      --bg: #0b0f14;
      --card: #111823;
      --line: #1f2a37;
      --text: #e6eaf2;
      --muted: #98a2b3;
      --accent: #7dd3fc;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      font-family: "Trebuchet MS", "Lucida Sans Unicode", "Segoe UI", sans-serif;
      background: radial-gradient(circle at 5% 0%, #122433 0%, transparent 38%), var(--bg);
      color: var(--text);
      line-height: 1.5;
    }}
    .wrap {{
      max-width: 980px;
      margin: 0 auto;
      padding: 24px 14px 34px;
    }}
    .hero {{
      border: 1px solid var(--line);
      border-radius: 14px;
      background: linear-gradient(130deg, #121b27 0%, #0f1a26 100%);
      padding: 18px;
    }}
    .hero h1 {{
      margin: 0;
      font-size: 27px;
    }}
    .hero p {{
      margin: 8px 0 0;
      color: var(--muted);
    }}
    .card {{
      margin-top: 12px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--card);
      padding: 14px;
    }}
    .card h2 {{
      margin: 0;
      font-size: 18px;
    }}
    ul {{
      margin: 10px 0 0;
      padding-left: 18px;
    }}
    li {{
      margin: 5px 0;
      color: #d9e3f0;
    }}
    .muted {{
      color: var(--muted);
      margin-top: 8px;
    }}
    pre {{
      margin: 8px 0 0;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #0b0f14;
      padding: 10px;
      overflow-x: auto;
    }}
    code {{
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
    }}
    a {{
      color: var(--accent);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .links {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 10px;
    }}
    .link {{
      display: inline-block;
      border: 1px solid #2f5160;
      border-radius: 10px;
      background: #0f1a26;
      color: var(--accent);
      text-decoration: none;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>Credits and Help</h1>
      <p>Warehouse Optimization and Robotics Operations Portfolio support page.</p>
      <p class="muted">Generated: {escape(generated_at)}</p>
      <div class="links">
        <a class="link" href="dashboard.html">Back to Dashboard</a>
        <a class="link" href="demo_script.md">demo_script.md</a>
        <a class="link" href="recruiter_one_pager.md">recruiter_one_pager.md</a>
      </div>
    </header>

    <section class="card">
      <h2>Credits</h2>
      <ul>
        <li>Program domain: Warehouse optimization, slotting strategy, robotics operations, and audit-readiness simulation.</li>
        <li>Primary stack: Python, pandas, numpy, matplotlib.</li>
        <li>Core reports and visuals are generated by pipeline modules in <code>src/</code>.</li>
        <li>Portfolio packaging and dashboard generation: <code>src/portfolio/portfolio.py</code>.</li>
      </ul>
    </section>

    <section class="card">
      <h2>Module Map</h2>
      <ul>
        <li>Week 2 pick path analysis: <code>src/pick_path/analyze_routes.py</code></li>
        <li>Week 3 slotting optimization: <code>src/slotting/heatmap.py</code></li>
        <li>Week 4 operations metrics: <code>src/operations/run_operations.py</code></li>
        <li>Week 5 audit pack: <code>src/audit_ready/run_audit_pack.py</code></li>
        <li>Week 6 scenario simulation: <code>src/scenarios/run_scenarios.py</code></li>
        <li>Week 7 portfolio pack: <code>src/portfolio/portfolio.py</code></li>
      </ul>
    </section>

    <section class="card">
      <h2>Help and Troubleshooting</h2>
      <ul>
        <li>Run the full pipeline first, then regenerate the portfolio dashboard.</li>
        <li>If a dashboard section is empty, verify the related CSV/PNG exists in <code>output/reports</code> or <code>output/charts</code>.</li>
        <li>Use the warning section in the dashboard to identify missing upstream files.</li>
      </ul>
      <pre><code>python main.py
python src/portfolio/portfolio.py</code></pre>
    </section>

    <section class="card">
      <h2>Key Artifacts</h2>
      <div class="links">
        <a class="link" href="assets/evidence_index.md">assets/evidence_index.md</a>
        <a class="link" href="assets/run_manifest.json">assets/run_manifest.json</a>
        <a class="link" href="assets/scenario_risk_report.md">assets/scenario_risk_report.md</a>
        <a class="link" href="assets/ops_brief.md">assets/ops_brief.md</a>
      </div>
    </section>
  </div>
</body>
</html>
"""


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
This portfolio demonstrates: pick path optimization -> slotting strategy -> operations KPIs -> audit-ready evidence -> scenario risk simulation.

## Delivered modules
- Week 2: pick path routing analysis and comparison KPIs.
- Week 3: ABC slotting and move-list impact analysis.
- Week 4: robotics fleet KPIs, alerts, and ops brief.
- Week 5: audit-ready inventory, cycle counts, exceptions, and run manifest.
- Week 6: Monte Carlo scenario risk with SLA breach probability.

## Primary Data
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
  A --> D[Week 4<br/>Operations<br/>robot_logs.csv]
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
2. `python src/slotting/heatmap.py`
3. `python src/operations/run_operations.py`
4. `python src/scenarios/run_scenarios.py`
5. `python src/audit_ready/run_audit_pack.py`
6. `python src/portfolio/portfolio.py`

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
    credits_path = PORTFOLIO_DIR / "credits.html"
    demo_path = PORTFOLIO_DIR / "demo_script.md"
    one_pager_path = PORTFOLIO_DIR / "recruiter_one_pager.md"
    architecture_path = DOCS_DIR / "architecture.md"

    write_text(dashboard_path, dashboard_html)
    write_text(credits_path, build_credits_page_html())
    write_text(demo_path, build_demo_script_md())
    write_text(one_pager_path, build_recruiter_one_pager_md())
    write_text(architecture_path, build_architecture_doc_md())

    print("DONE: portfolio pack generated")
    print(f" - {dashboard_path.relative_to(PROJECT_ROOT).as_posix()}")
    print(f" - {credits_path.relative_to(PROJECT_ROOT).as_posix()}")
    print(f" - {demo_path.relative_to(PROJECT_ROOT).as_posix()}")
    print(f" - {one_pager_path.relative_to(PROJECT_ROOT).as_posix()}")
    print(f" - {architecture_path.relative_to(PROJECT_ROOT).as_posix()}")

    if missing_inputs:
        print("WARN: Missing upstream Data (dashboard shows partial data):")
        for item in missing_inputs:
            print(f" - {item}")


if __name__ == "__main__":
    main()
