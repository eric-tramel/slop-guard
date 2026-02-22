"""CLI entry point for the ``sg`` prose linter.

Usage examples::

    # Lint files by name
    sg README.md docs/*.md

    # Lint from stdin
    cat essay.txt | sg
    echo "This is a crucial paradigm shift." | sg -

    # Glob expansion (shell does it, but also works with recursive globs)
    sg **/*.md

    # Machine-readable JSON output
    sg -j report.md

    # Verbose: show individual violations
    sg -v draft.md

    # Set exit code threshold (default: 0 = always exit 0 unless error)
    sg -t 60 draft.md   # exit 1 if any file scores below 60

    # Quiet mode: only print filenames that fail the threshold
    sg -q -t 60 docs/*.md
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import TextIO

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
) -> dict:
    """Run analysis and attach the source label."""
    result = _analyze(text, hyperparameters)
    result["source"] = label
    return result


def _analyze_file(path: Path, hyperparameters: Hyperparameters) -> dict:
    """Read a file and analyze its contents."""
    text = path.read_text(encoding="utf-8")
    return _analyze_text(text, str(path), hyperparameters)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    p = argparse.ArgumentParser(
        prog="sg",
        description="Prose linter for AI slop patterns.",
        epilog="Reads from stdin when no files are given or when '-' is specified.",
    )
    p.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="Files to lint (supports globs). Use '-' for stdin.",
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
        "-c", "--counts",
        action="store_true",
        default=False,
        help="Show per-rule hit counts in the summary line.",
    )
    p.add_argument(
        "-g", "--glob",
        action="append",
        default=[],
        metavar="PATTERN",
        dest="globs",
        help="Additional glob patterns to expand (may be repeated).",
    )
    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _resolve_inputs(args: argparse.Namespace) -> list[str | Path]:
    """Resolve file arguments and globs into an ordered list of inputs.

    Returns a list of ``Path`` objects for files and the string ``"-"`` for
    stdin.
    """
    inputs: list[str | Path] = []

    # Collect explicit file args
    for f in args.files:
        if f == "-":
            inputs.append("-")
        else:
            # Try glob expansion (handles cases where shell didn't expand)
            expanded = sorted(glob.glob(f, recursive=True))
            if expanded:
                inputs.extend(Path(p) for p in expanded if Path(p).is_file())
            else:
                # Treat as literal path
                inputs.append(Path(f))

    # Collect -g/--glob patterns
    for pattern in args.globs:
        expanded = sorted(glob.glob(pattern, recursive=True))
        inputs.extend(Path(p) for p in expanded if Path(p).is_file())

    return inputs


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

    # Default to stdin when nothing is provided
    if not inputs:
        inputs = ["-"]

    results: list[dict] = []
    hp = HYPERPARAMETERS

    for src in inputs:
        if src == "-":
            if sys.stdin.isatty() and not args.files:
                parser.print_usage(sys.stderr)
                print("sg: reading from stdin (Ctrl-D to finish)", file=sys.stderr)
            text = sys.stdin.read()
            result = _analyze_text(text, "<stdin>", hp)
        else:
            assert isinstance(src, Path)
            if not src.is_file():
                print(f"sg: {src}: No such file", file=sys.stderr)
                continue
            try:
                result = _analyze_file(src, hp)
            except (OSError, UnicodeDecodeError) as exc:
                print(f"sg: {src}: {exc}", file=sys.stderr)
                continue
        results.append(result)

    if not results:
        return EXIT_ERROR

    # --- Output ---
    if args.json:
        out = results if len(results) > 1 else results[0]
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for result in results:
            label = result["source"]
            fails_threshold = (
                args.threshold > 0 and result["score"] < args.threshold
            )
            if args.quiet and not fails_threshold:
                continue
            print(_format_score_line(label, result, show_counts=args.counts))
            if args.verbose:
                if result["violations"]:
                    _print_violations(result)
                if result["advice"]:
                    _print_advice(result)

    # --- Exit code ---
    if args.threshold > 0:
        if any(r["score"] < args.threshold for r in results):
            return EXIT_THRESHOLD_FAILURE

    return EXIT_OK


def main() -> None:
    """Thin wrapper that calls ``sys.exit`` with the CLI return code."""
    sys.exit(cli_main())
