# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp"]
# ///
"""Benchmark per-rule compute time across synthetic text lengths.

Example:
    uv run benchmark/compute-time.py --length-mode log --num-lengths 80 --repeats 5
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import random
import sys
import time
from pathlib import Path
from typing import TypeAlias

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from slop_guard.analysis import AnalysisDocument  # noqa: E402
from slop_guard.rules.base import Rule, RuleConfig  # noqa: E402
from slop_guard.rules import build_default_rules  # noqa: E402

RuleList: TypeAlias = list[Rule[RuleConfig]]
BenchmarkRecord: TypeAlias = dict[str, str | int | float]

_WORD_BANK: tuple[str, ...] = (
    "ability",
    "about",
    "access",
    "across",
    "action",
    "adapt",
    "after",
    "agent",
    "align",
    "analysis",
    "anchor",
    "answer",
    "api",
    "approach",
    "area",
    "argue",
    "array",
    "article",
    "aspect",
    "assert",
    "assign",
    "assist",
    "assume",
    "async",
    "audit",
    "author",
    "avoid",
    "backlog",
    "balance",
    "baseline",
    "batch",
    "before",
    "behavior",
    "between",
    "binary",
    "branch",
    "build",
    "cache",
    "call",
    "capture",
    "case",
    "change",
    "check",
    "client",
    "close",
    "cloud",
    "code",
    "column",
    "command",
    "comment",
    "commit",
    "common",
    "compare",
    "compile",
    "compute",
    "config",
    "confirm",
    "connect",
    "constant",
    "context",
    "control",
    "convert",
    "count",
    "create",
    "critical",
    "current",
    "cursor",
    "cycle",
    "data",
    "debug",
    "define",
    "delta",
    "deploy",
    "design",
    "detail",
    "detect",
    "device",
    "direct",
    "document",
    "draft",
    "duration",
    "editor",
    "effect",
    "engine",
    "ensure",
    "entry",
    "error",
    "event",
    "exact",
    "example",
    "expect",
    "export",
    "factor",
    "feature",
    "field",
    "filter",
    "final",
    "first",
    "flag",
    "focus",
    "format",
    "frame",
    "function",
    "future",
    "gather",
    "general",
    "goal",
    "graph",
    "group",
    "handle",
    "helper",
    "history",
    "human",
    "hyper",
    "idea",
    "image",
    "import",
    "include",
    "index",
    "infer",
    "input",
    "insight",
    "item",
    "iterate",
    "join",
    "json",
    "key",
    "label",
    "large",
    "layer",
    "learn",
    "level",
    "limit",
    "line",
    "lint",
    "list",
    "local",
    "logic",
    "loop",
    "match",
    "matrix",
    "measure",
    "memory",
    "merge",
    "message",
    "method",
    "metric",
    "model",
    "module",
    "monitor",
    "move",
    "native",
    "network",
    "note",
    "number",
    "object",
    "observe",
    "offset",
    "option",
    "order",
    "output",
    "package",
    "page",
    "pair",
    "panel",
    "parallel",
    "parse",
    "pattern",
    "perform",
    "phase",
    "pipeline",
    "plan",
    "point",
    "policy",
    "position",
    "predict",
    "prefix",
    "prepare",
    "present",
    "primary",
    "print",
    "process",
    "profile",
    "project",
    "prompt",
    "protect",
    "prove",
    "public",
    "query",
    "queue",
    "quick",
    "random",
    "range",
    "rank",
    "rate",
    "record",
    "reduce",
    "refactor",
    "reference",
    "region",
    "registry",
    "reject",
    "release",
    "render",
    "report",
    "request",
    "resolve",
    "result",
    "review",
    "rule",
    "sample",
    "scale",
    "score",
    "script",
    "search",
    "section",
    "select",
    "series",
    "service",
    "session",
    "shape",
    "signal",
    "simple",
    "size",
    "slice",
    "source",
    "split",
    "stable",
    "stack",
    "stage",
    "state",
    "step",
    "store",
    "stream",
    "strict",
    "string",
    "style",
    "summary",
    "system",
    "table",
    "target",
    "task",
    "template",
    "test",
    "text",
    "theme",
    "thread",
    "time",
    "token",
    "topic",
    "trace",
    "track",
    "train",
    "type",
    "update",
    "usage",
    "value",
    "vector",
    "verify",
    "version",
    "view",
    "visual",
    "weight",
    "window",
    "workflow",
    "write",
)

_SENTENCE_WORD_COUNTS: tuple[int, ...] = (8, 11, 15, 10, 14, 9, 13, 12, 16)


def parse_args() -> argparse.Namespace:
    """Parse benchmark CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Measure forward-pass compute time for every default configured rule "
            "across synthetic text lengths."
        )
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=1,
        help="Minimum word count (inclusive).",
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=10_000,
        help="Maximum word count (inclusive).",
    )
    parser.add_argument(
        "--length-mode",
        choices=("log", "linear", "all"),
        default="all",
        help=(
            "Length sampling strategy. 'all' includes every integer length in "
            "the range; 'linear' and 'log' use --num-lengths points."
        ),
    )
    parser.add_argument(
        "--num-lengths",
        type=int,
        default=80,
        help="Number of sampled lengths when --length-mode is log or linear.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Timed runs per rule and text length.",
    )
    parser.add_argument(
        "--warmup-runs",
        type=int,
        default=1,
        help="Untimed warmup runs per rule and text length.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Random seed used for synthetic word generation.",
    )
    parser.add_argument(
        "--output",
        default="benchmark/output/rule_compute_time.jsonl",
        help="Output JSONL path.",
    )
    return parser.parse_args()


def build_lengths(
    *,
    min_words: int,
    max_words: int,
    length_mode: str,
    num_lengths: int,
) -> list[int]:
    """Build sorted text lengths according to the chosen sampling mode."""
    if min_words < 1:
        raise ValueError("--min-words must be >= 1")
    if max_words < min_words:
        raise ValueError("--max-words must be >= --min-words")
    if length_mode in {"log", "linear"} and num_lengths < 2:
        raise ValueError("--num-lengths must be >= 2 when using log or linear mode")

    if length_mode == "all":
        return list(range(min_words, max_words + 1))
    if min_words == max_words:
        return [min_words]
    if length_mode == "linear":
        step = (max_words - min_words) / (num_lengths - 1)
        return sorted(
            {min_words, max_words}
            | {int(round(min_words + (idx * step))) for idx in range(num_lengths)}
        )
    if length_mode == "log":
        log_min = math.log(min_words)
        log_max = math.log(max_words)
        values = {min_words, max_words}
        for idx in range(num_lengths):
            ratio = idx / (num_lengths - 1)
            raw = math.exp(log_min + ratio * (log_max - log_min))
            values.add(int(round(raw)))
        return sorted(values)
    raise ValueError(f"Unsupported --length-mode: {length_mode}")


def build_word_stream(*, seed: int, max_words: int) -> list[str]:
    """Generate a deterministic random sequence of real words."""
    if max_words < 1:
        raise ValueError("max_words must be >= 1")
    rng = random.Random(seed)
    return rng.choices(_WORD_BANK, k=max_words)


def compose_text(words: list[str]) -> str:
    """Compose sentence and paragraph structure from plain words."""
    sentences: list[str] = []
    cursor = 0
    sentence_index = 0
    while cursor < len(words):
        span = _SENTENCE_WORD_COUNTS[sentence_index % len(_SENTENCE_WORD_COUNTS)]
        segment = words[cursor : cursor + span]
        cursor += span
        if not segment:
            break
        ending = "." if (sentence_index + 1) % 4 else "?"
        sentences.append(f"{' '.join(segment)}{ending}")
        sentence_index += 1

    paragraphs: list[str] = []
    for start in range(0, len(sentences), 5):
        paragraphs.append(" ".join(sentences[start : start + 5]))
    return "\n\n".join(paragraphs)


def time_rule(
    *,
    rule: Rule[RuleConfig],
    document: AnalysisDocument,
    repeats: int,
    warmup_runs: int,
) -> list[float]:
    """Measure one rule over repeated runs and return elapsed milliseconds."""
    for _ in range(warmup_runs):
        rule.forward(document)

    elapsed_ms: list[float] = []
    for _ in range(repeats):
        start_ns = time.perf_counter_ns()
        rule.forward(document)
        end_ns = time.perf_counter_ns()
        elapsed_ms.append((end_ns - start_ns) / 1_000_000.0)
    return elapsed_ms


def benchmark_rules(
    *,
    rules: RuleList,
    lengths: list[int],
    word_stream: list[str],
    repeats: int,
    warmup_runs: int,
    output_path: Path,
) -> int:
    """Benchmark each rule/length pair and write per-run records as JSONL."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0

    with output_path.open("w", encoding="utf-8") as handle:
        gc_enabled = gc.isenabled()
        gc.disable()
        try:
            for word_count in lengths:
                text = compose_text(word_stream[:word_count])
                document = AnalysisDocument.from_text(text)
                for rule in rules:
                    timings = time_rule(
                        rule=rule,
                        document=document,
                        repeats=repeats,
                        warmup_runs=warmup_runs,
                    )
                    for run_index, elapsed in enumerate(timings, start=1):
                        record: BenchmarkRecord = {
                            "rule": rule.__class__.__name__,
                            "rule_key": rule.name,
                            "count_key": rule.count_key,
                            "level": rule.level.value,
                            "word_count": word_count,
                            "run": run_index,
                            "time_ms": elapsed,
                        }
                        handle.write(json.dumps(record, sort_keys=True) + "\n")
                        row_count += 1
        finally:
            if gc_enabled:
                gc.enable()

    return row_count


def main() -> None:
    """Run the compute-time benchmark and persist JSONL rows."""
    args = parse_args()
    lengths = build_lengths(
        min_words=args.min_words,
        max_words=args.max_words,
        length_mode=args.length_mode,
        num_lengths=args.num_lengths,
    )
    rules = build_default_rules()
    word_stream = build_word_stream(seed=args.seed, max_words=args.max_words)
    output_path = Path(args.output)

    row_count = benchmark_rules(
        rules=rules,
        lengths=lengths,
        word_stream=word_stream,
        repeats=args.repeats,
        warmup_runs=args.warmup_runs,
        output_path=output_path,
    )
    print(
        "Benchmark complete:",
        f"{len(rules)} rules, {len(lengths)} text lengths, {args.repeats} repeats,",
        f"{row_count} rows -> {output_path}",
    )


if __name__ == "__main__":
    main()
