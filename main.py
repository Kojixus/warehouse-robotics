from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelineStep:
    key: str
    label: str
    script_path: Path


PROJECT_ROOT = Path(__file__).resolve().parent
PIPELINE_STEPS: tuple[PipelineStep, ...] = (
    PipelineStep("pick_path", "Pick Path Analysis", PROJECT_ROOT / "src" / "pick_path" / "analyze_routes.py"),
    PipelineStep("slotting", "Slotting Optimization", PROJECT_ROOT / "src" / "slotting" / "run_slotting.py"),
    PipelineStep("operations", "Operations", PROJECT_ROOT / "src" / "operations" / "run_operations.py"),
    PipelineStep("scenarios", "Scenario Simulation", PROJECT_ROOT / "src" / "scenarios" / "run_scenarios.py"),
    PipelineStep("audit_pack", "Audit Pack", PROJECT_ROOT / "src" / "audit_ready" / "run_audit_pack.py"),
    PipelineStep("portfolio_pack", "Portfolio Pack", PROJECT_ROOT / "src" / "portfolio" / "run_portfolio_pack.py"),
)
STEP_ALIASES: dict[str, str] = {
    "control_tower": "operations",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Warehouse Robotics pipeline from one command. "
            "By default, all steps run in dependency-safe order."
        )
    )
    parser.add_argument(
        "steps",
        nargs="*",
        help="Optional subset of step keys to run (example: pick_path slotting).",
    )
    parser.add_argument(
        "--skip",
        nargs="*",
        default=[],
        help="Optional step keys to skip.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available step keys and exit.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue to the next step if one step fails.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use when running child scripts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would run without executing scripts.",
    )
    return parser.parse_args()


def validate_step_keys(keys: set[str]) -> None:
    known = {step.key for step in PIPELINE_STEPS}
    unknown = sorted(keys - known)
    if unknown:
        raise ValueError(
            f"Unknown step key(s): {', '.join(unknown)}. Use --list to see valid step keys."
        )


def normalize_step_key(key: str) -> str:
    return STEP_ALIASES.get(key, key)


def select_steps(include: list[str], skip: list[str]) -> list[PipelineStep]:
    include_set_raw = set(include) if include else {step.key for step in PIPELINE_STEPS}
    skip_set_raw = set(skip)

    include_set = {normalize_step_key(key) for key in include_set_raw}
    skip_set = {normalize_step_key(key) for key in skip_set_raw}

    validate_step_keys(include_set | skip_set)

    selected = [step for step in PIPELINE_STEPS if step.key in include_set and step.key not in skip_set]
    if not selected:
        raise ValueError("No steps selected to run. Check your step filters.")
    return selected


def list_steps() -> None:
    print("Available steps:")
    for step in PIPELINE_STEPS:
        print(f" - {step.key:<13} {step.label} ({step.script_path.relative_to(PROJECT_ROOT).as_posix()})")


def run_step(step: PipelineStep, python_executable: str, dry_run: bool) -> int:
    if not step.script_path.exists():
        print(f"[ERROR] Missing script for step '{step.key}': {step.script_path}", file=sys.stderr)
        return 2

    cmd = [python_executable, str(step.script_path)]
    print(f"\n==> Running {step.label} [{step.key}]")
    print("    " + " ".join(cmd))

    if dry_run:
        return 0

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, check=False)
    return result.returncode


def main() -> int:
    args = parse_args()

    if args.list:
        list_steps()
        return 0

    try:
        selected_steps = select_steps(args.steps, args.skip)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    failures: list[tuple[str, int]] = []
    for step in selected_steps:
        rc = run_step(step, python_executable=args.python, dry_run=args.dry_run)
        if rc != 0:
            failures.append((step.key, rc))
            print(f"[FAIL] Step '{step.key}' exited with code {rc}", file=sys.stderr)
            if not args.continue_on_error:
                break

    if failures:
        print("\nPipeline finished with failures:", file=sys.stderr)
        for key, rc in failures:
            print(f" - {key}: exit code {rc}", file=sys.stderr)
        return 1

    print("\nPipeline completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
