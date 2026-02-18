from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable


DEFAULT_CONFIG_PATH = "config/scenarios.json"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_GLOBAL_KEYS = {
    "shift_minutes",
    "base_servers",
    "start_x",
    "start_y",
    "pick_seconds_per_line",
    "travel_seconds_per_unit",
    "base_congestion_mean_min",
    "base_congestion_sigma_min",
    "base_fault_prob_per_order",
    "fault_delay_min_min",
    "fault_delay_max_min",
    "capacity_penalty_scale_min",
    "congestion_gain",
    "fault_prob_gain",
    "sla_breach_threshold_pct",
    "monte_carlo_runs",
    "base_seed",
}

REQUIRED_SCENARIO_KEYS = {
    "name",
    "demand_multiplier",
    "robots_available_pct",
    "fault_multiplier",
    "queue_delay_multiplier",
}


def _resolve_config_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    cwd_path = Path.cwd() / candidate
    if cwd_path.exists():
        return cwd_path
    return PROJECT_ROOT / candidate


def _missing_keys(data: Dict[str, Any], required: Iterable[str]) -> set[str]:
    return set(required) - set(data.keys())


def _validate_config(config: Dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError("Config must be a JSON object")

    missing_top = _missing_keys(config, ("global", "scenarios"))
    if missing_top:
        raise ValueError(f"Config missing top-level keys: {sorted(missing_top)}")

    global_cfg = config["global"]
    if not isinstance(global_cfg, dict):
        raise ValueError("'global' must be an object")
    missing_global = _missing_keys(global_cfg, REQUIRED_GLOBAL_KEYS)
    if missing_global:
        raise ValueError(f"Config 'global' missing keys: {sorted(missing_global)}")

    scenarios = config["scenarios"]
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("'scenarios' must be a non-empty array")

    for idx, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            raise ValueError(f"Scenario at index {idx} must be an object")
        missing_scenario = _missing_keys(scenario, REQUIRED_SCENARIO_KEYS)
        if missing_scenario:
            raise ValueError(f"Scenario at index {idx} missing keys: {sorted(missing_scenario)}")
        if not str(scenario["name"]).strip():
            raise ValueError(f"Scenario at index {idx} has an empty name")
        if float(scenario["demand_multiplier"]) < 0.0:
            raise ValueError(f"Scenario '{scenario['name']}' has negative demand_multiplier")
        robots_pct = float(scenario["robots_available_pct"])
        if robots_pct <= 0.0 or robots_pct > 1.0:
            raise ValueError(f"Scenario '{scenario['name']}' robots_available_pct must be in (0, 1]")
        if float(scenario["fault_multiplier"]) < 0.0:
            raise ValueError(f"Scenario '{scenario['name']}' has negative fault_multiplier")
        if float(scenario["queue_delay_multiplier"]) < 0.0:
            raise ValueError(f"Scenario '{scenario['name']}' has negative queue_delay_multiplier")

    if int(global_cfg["shift_minutes"]) <= 0:
        raise ValueError("'shift_minutes' must be > 0")
    if int(global_cfg["base_servers"]) <= 0:
        raise ValueError("'base_servers' must be > 0")
    if int(global_cfg["monte_carlo_runs"]) <= 0:
        raise ValueError("'monte_carlo_runs' must be > 0")
    if float(global_cfg["travel_seconds_per_unit"]) < 0.0:
        raise ValueError("'travel_seconds_per_unit' must be >= 0")
    if float(global_cfg["pick_seconds_per_line"]) < 0.0:
        raise ValueError("'pick_seconds_per_line' must be >= 0")
    if float(global_cfg["fault_delay_min_min"]) < 0.0 or float(global_cfg["fault_delay_max_min"]) < 0.0:
        raise ValueError("Fault delay bounds must be >= 0")
    if float(global_cfg["fault_delay_min_min"]) > float(global_cfg["fault_delay_max_min"]):
        raise ValueError("'fault_delay_min_min' cannot be greater than 'fault_delay_max_min'")
    if float(global_cfg["capacity_penalty_scale_min"]) < 0.0:
        raise ValueError("'capacity_penalty_scale_min' must be >= 0")
    if float(global_cfg["congestion_gain"]) < 0.0:
        raise ValueError("'congestion_gain' must be >= 0")
    if float(global_cfg["fault_prob_gain"]) < 0.0:
        raise ValueError("'fault_prob_gain' must be >= 0")


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    resolved_path = _resolve_config_path(path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Missing config file: {resolved_path}")
    with resolved_path.open("r", encoding="utf-8") as f:
        config = json.load(f)
    _validate_config(config)
    return config
