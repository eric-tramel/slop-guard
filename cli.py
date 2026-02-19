#!/usr/bin/env python3
"""Standalone CLI for slop-guard.  Zero external dependencies.

Usage:
    python cli.py README.md [file2.md ...]
    cat draft.md | python cli.py
    python cli.py --json README.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from slop_guard import HYPERPARAMETERS, _analyze

# -- colors (when tty) -----------------------------------------------------

_BAND_COLORS = {
    "clean": "\033[32m",
    "light": "\033[33m",
    "moderate": "\033[38;5;208m",
    "heavy": "\033[31m",
    "saturated": "\033[91m",
}
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"


def _print_result(result: dict[str, Any], label: str) -> None:
    color = sys.stderr.isatty()
    score = result["score"]
    band = result["band"]
    words = result["word_count"]

    bc = _BAND_COLORS.get(band, "") if color else ""
    r = _RESET if color else ""
    b = _BOLD if color else ""
    d = _DIM if color else ""

    print(
        f"\n{b}{label}{r}  {bc}{score}/100 {band}{r}  {d}({words} words){r}",
        file=sys.stderr,
    )

    for v in result.get("violations", []):
        pen = v.get("penalty", 0)
        rule = v.get("rule", "")
        match = v.get("match", "")
        print(f"  {bc}{pen:+d}{r}  {rule}: {match}", file=sys.stderr)

    advice = result.get("advice", [])
    if advice:
        print(f"\n{b}Advice:{r}", file=sys.stderr)
        for a in advice:
            print(f"  • {a}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="slop-guard", description="Detect AI slop patterns in prose."
    )
    parser.add_argument("files", nargs="*", help="Files to analyze (stdin if omitted)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON to stdout")
    args = parser.parse_args()

    if not args.files and sys.stdin.isatty():
        parser.print_help(sys.stderr)
        sys.exit(2)

    targets: list[tuple[str, str]] = []
    exit_code = 0

    if args.files:
        for fp in args.files:
            p = Path(fp)
            if not p.is_file():
                print(f"slop-guard: {fp}: not found", file=sys.stderr)
                exit_code = 2
                continue
            targets.append((fp, p.read_text(encoding="utf-8")))
    else:
        targets.append(("stdin", sys.stdin.read()))

    results = []
    for label, text in targets:
        result = _analyze(text, HYPERPARAMETERS)
        result["file"] = label
        results.append(result)
        if not args.json:
            _print_result(result, label)

    if args.json:
        out = results[0] if len(results) == 1 else results
        print(json.dumps(out, indent=2))

    if not exit_code and any(r["band"] not in ("clean", "light") for r in results):
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
