"""CLI entry point for the ``sg`` prose linter.

Usage examples::

    # Lint files by name
    sg README.md docs/*.md

    # Lint inline text
    sg "This is some test text"

    # Lint from stdin
    cat essay.txt | sg -

    # Machine-readable JSON output
    sg -j report.md

    # Verbose: show individual violations
    sg -v draft.md

    # Score only
    sg -s draft.md

    # Use a custom JSONL rule config
    sg -c config.jsonl draft.md

    # Set exit code threshold (default: 0 = always exit 0 unless error)
    sg -t 60 draft.md   # exit 1 if any file scores below 60

    # Quiet mode: only print filenames that fail the threshold
    sg -q -t 60 docs/*.md
"""


import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TextIO, TypeAlias

from .rules import Pipeline
from .server import HYPERPARAMETERS, Hyperparameters, _analyze

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_OK = 0
EXIT_THRESHOLD_FAILURE = 1
EXIT_ERROR = 2

# ---------------------------------------------------------------------------
# Band decorations for terminal output
# ---------------------------------------------------------------------------

_BAND_SYMBOLS: dict[str, str] = {
    "clean": ".",
    "light": "*",
    "moderate": "!",
    "heavy": "!!",
    "saturated": "!!!",
}

InputValue: TypeAlias = str | Path


@dataclass(frozen=True)
class InputTarget:
    """Typed representation of a CLI input target."""

    kind: Literal["file", "stdin", "text"]
    value: InputValue
    label: str


def _format_score_line(
    label: str,
    result: dict,
    *,
    show_counts: bool = False,
) -> str:
    """Build a one-line summary for a single analyzed input."""
    score = result["score"]
    band = result["band"]
    wc = result["word_count"]
    sym = _BAND_SYMBOLS.get(band, "?")
    line = f"{label}: {score}/100 [{band}] ({wc} words) {sym}"
    if show_counts:
        active = {k: v for k, v in result["counts"].items() if v}
        if active:
            parts = " ".join(f"{k}={v}" for k, v in active.items())
            line += f"  ({parts})"
    return line


def _print_violations(result: dict, file: TextIO = sys.stdout) -> None:
    """Print individual violations grouped under the result."""
    for v in result["violations"]:
        rule = v["rule"]
        match = v["match"]
        penalty = v["penalty"]
        ctx = v["context"]
        print(f"  {rule}: {match} ({penalty})  {ctx}", file=file)


def _print_advice(result: dict, file: TextIO = sys.stdout) -> None:
    """Print deduped advice list."""
    for item in result["advice"]:
        print(f"  - {item}", file=file)


# ---------------------------------------------------------------------------
# Core analysis dispatch
# ---------------------------------------------------------------------------


def _analyze_text(
    text: str,
    label: str,
    hyperparameters: Hyperparameters,
    pipeline: Pipeline,
) -> dict:
    """Run analysis and attach the source label."""
    result = _analyze(text, hyperparameters, pipeline=pipeline)
    result["source"] = label
    return result


def _analyze_file(
    path: Path,
    hyperparameters: Hyperparameters,
    pipeline: Pipeline,
) -> dict:
    """Read a file and analyze its contents."""
    text = path.read_text(encoding="utf-8")
    return _analyze_text(text, str(path), hyperparameters, pipeline)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    p = argparse.ArgumentParser(
        prog="sg",
        description="Prose linter for AI slop patterns.",
        epilog="Pass file paths, '-' for stdin, or quoted inline text.",
    )
    p.add_argument(
        "inputs",
        nargs="+",
        metavar="INPUT",
        help="Inputs to lint: files, '-' for stdin, or quoted inline text.",
    )
    p.add_argument(
        "-j", "--json",
        action="store_true",
        default=False,
        help="Output results as JSON.",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Show individual violations and advice.",
    )
    p.add_argument(
        "-q", "--quiet",
        action="store_true",
        default=False,
        help="Only print sources that fail the threshold.",
    )
    p.add_argument(
        "-t", "--threshold",
        type=int,
        default=0,
        metavar="SCORE",
        help="Minimum passing score (0-100). Exit 1 if any input scores below this.",
    )
    p.add_argument(
        "-c", "--config",
        default=None,
        metavar="JSONL",
        help="Path to JSONL rule configuration. Defaults to packaged settings.",
    )
    p.add_argument(
        "-s", "--score-only",
        action="store_true",
        default=False,
        help="Print score only.",
    )
    p.add_argument(
        "--counts",
        action="store_true",
        default=False,
        help="Show per-rule hit counts in the summary line.",
    )
    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _is_inline_text_argument(value: str) -> bool:
    """Return whether a positional argument should be treated as inline text."""
    return any(ch.isspace() for ch in value)


def _resolve_inputs(args: argparse.Namespace) -> list[InputTarget]:
    """Resolve positional args into typed input targets."""
    inputs: list[InputTarget] = []
    for index, raw in enumerate(args.inputs, start=1):
        if raw == "-":
            inputs.append(InputTarget(kind="stdin", value=raw, label="<stdin>"))
            continue
        candidate_path = Path(raw)
        if candidate_path.is_file():
            inputs.append(
                InputTarget(kind="file", value=candidate_path, label=str(candidate_path))
            )
            continue
        if _is_inline_text_argument(raw):
            inputs.append(InputTarget(kind="text", value=raw, label=f"<text:{index}>"))
            continue
        inputs.append(InputTarget(kind="file", value=candidate_path, label=str(candidate_path)))
    return inputs


def _emit_result(result: dict, args: argparse.Namespace) -> None:
    """Print one analyzed result immediately."""
    fails_threshold = args.threshold > 0 and result["score"] < args.threshold
    if args.quiet and not fails_threshold:
        return
    if args.score_only:
        print(result["score"], flush=True)
        return

    print(
        _format_score_line(result["source"], result, show_counts=args.counts),
        flush=True,
    )
    if args.verbose:
        if result["violations"]:
            _print_violations(result)
        if result["advice"]:
            _print_advice(result)


def cli_main(argv: list[str] | None = None) -> int:
    """Entry point for the ``sg`` command.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Exit code suitable for ``sys.exit``.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    inputs = _resolve_inputs(args)

    results: list[dict] = []
    threshold_failed = False
    hp = HYPERPARAMETERS
    pipeline = Pipeline.from_jsonl(args.config)

    for target in inputs:
        if target.kind == "stdin":
            text = sys.stdin.read()
            result = _analyze_text(text, target.label, hp, pipeline)
        elif target.kind == "text":
            assert isinstance(target.value, str)
            result = _analyze_text(target.value, target.label, hp, pipeline)
        else:
            assert isinstance(target.value, Path)
            path = target.value
            if not path.is_file():
                print(f"sg: {path}: No such file", file=sys.stderr)
                continue
            try:
                result = _analyze_file(path, hp, pipeline)
            except (OSError, UnicodeDecodeError) as exc:
                print(f"sg: {path}: {exc}", file=sys.stderr)
                continue

        results.append(result)
        if args.threshold > 0 and result["score"] < args.threshold:
            threshold_failed = True

        if not args.json:
            _emit_result(result, args)

    if not results:
        return EXIT_ERROR

    # --- Output ---
    if args.json:
        out = results if len(results) > 1 else results[0]
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")

    # --- Exit code ---
    if threshold_failed:
        return EXIT_THRESHOLD_FAILURE

    return EXIT_OK


def main() -> None:
    """Thin wrapper that calls ``sys.exit`` with the CLI return code."""
    sys.exit(cli_main())
