# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""CLI entry point for the slop-guard evaluation harness.

Usage:
    uv run eval/cli.py run --agent claude_code
    uv run eval/cli.py run --agent codex --max-revisions 5
    uv run eval/cli.py report eval/output/results_claude_code.jsonl
    uv run eval/cli.py compare results_claude_code.jsonl results_codex.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as a script from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from eval.analyze import build_report, load_results, print_report
from eval.harness import Agent, HarnessConfig, run_experiment
from eval.prompts import CORE_TASKS, Genre, tasks_by_genre


def _build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="sg-eval",
        description="Evaluation harness for measuring slop-guard effectiveness.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- run ---
    run_parser = subparsers.add_parser(
        "run", help="Run the evaluation experiment."
    )
    run_parser.add_argument(
        "--agent",
        required=True,
        choices=[a.value for a in Agent],
        help="Agent backend to evaluate.",
    )
    run_parser.add_argument(
        "--genre",
        default=None,
        choices=[g.value for g in Genre],
        help="Restrict to a single genre (default: all).",
    )
    run_parser.add_argument(
        "--max-revisions",
        type=int,
        default=3,
        help="Maximum revision rounds in treatment (default: 3).",
    )
    run_parser.add_argument(
        "--target-score",
        type=int,
        default=80,
        help="Slop-guard score target for convergence (default: 80).",
    )
    run_parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Per-invocation timeout in seconds (default: 120).",
    )
    run_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("eval/output"),
        help="Directory for result JSONL files (default: eval/output).",
    )
    run_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Custom slop-guard JSONL config for treatment condition.",
    )

    # --- report ---
    report_parser = subparsers.add_parser(
        "report", help="Generate a report from result JSONL."
    )
    report_parser.add_argument(
        "results",
        type=Path,
        help="Path to a results JSONL file.",
    )
    report_parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of human-readable text.",
    )

    # --- compare ---
    compare_parser = subparsers.add_parser(
        "compare", help="Compare results across two agents."
    )
    compare_parser.add_argument(
        "file_a",
        type=Path,
        help="First results JSONL file.",
    )
    compare_parser.add_argument(
        "file_b",
        type=Path,
        help="Second results JSONL file.",
    )
    compare_parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of human-readable text.",
    )

    return parser


def _cmd_run(args: argparse.Namespace) -> None:
    """Execute the 'run' subcommand."""
    agent = Agent(args.agent)
    tasks = CORE_TASKS
    if args.genre:
        tasks = tasks_by_genre(Genre(args.genre))
        if not tasks:
            print(f"No tasks found for genre: {args.genre}", file=sys.stderr)
            sys.exit(2)

    config = HarnessConfig(
        agent=agent,
        max_revisions=args.max_revisions,
        target_score=args.target_score,
        timeout_seconds=args.timeout,
        output_dir=args.output_dir,
        slop_guard_config=args.config,
    )

    print(f"Running {len(tasks)} tasks with agent={agent.value}, "
          f"max_revisions={config.max_revisions}")
    results = run_experiment(tasks, config)

    control_scores = [
        r.final_draft.slop_result.get("score", 0)
        for r in results if r.condition == "control"
    ]
    treatment_scores = [
        r.final_draft.slop_result.get("score", 0)
        for r in results if r.condition == "treatment"
    ]

    def _safe_mean(vals: list) -> float:
        return sum(float(v) for v in vals) / len(vals) if vals else 0.0

    print(f"\nQuick summary:")
    print(f"  Control mean score:   {_safe_mean(control_scores):.1f}")
    print(f"  Treatment mean score: {_safe_mean(treatment_scores):.1f}")
    output_path = config.output_dir / f"results_{agent.value}.jsonl"
    print(f"  Results written to:   {output_path}")


def _cmd_report(args: argparse.Namespace) -> None:
    """Execute the 'report' subcommand."""
    records = load_results(args.results)
    report = build_report(records)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)


def _cmd_compare(args: argparse.Namespace) -> None:
    """Execute the 'compare' subcommand."""
    records_a = load_results(args.file_a)
    records_b = load_results(args.file_b)

    report_a = build_report(records_a)
    report_b = build_report(records_b)

    agents = set()
    for r in records_a:
        agents.add(str(r.get("agent", "agent_a")))
    agent_a = agents.pop() if agents else "agent_a"
    agents = set()
    for r in records_b:
        agents.add(str(r.get("agent", "agent_b")))
    agent_b = agents.pop() if agents else "agent_b"

    combined = {"agents": {agent_a: report_a, agent_b: report_b}}

    if args.json:
        print(json.dumps(combined, indent=2))
    else:
        print(f"=== {agent_a} ===")
        print_report(report_a)
        print()
        print(f"=== {agent_b} ===")
        print_report(report_b)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the evaluation CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    commands = {
        "run": _cmd_run,
        "report": _cmd_report,
        "compare": _cmd_compare,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
