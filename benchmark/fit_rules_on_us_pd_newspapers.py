# /// script
# requires-python = ">=3.11"
# dependencies = ["datasets", "huggingface_hub", "mcp"]
# ///
"""Fit all default slop-guard rules on a benchmark corpus and print config diffs.

Example:
    uv run benchmark/fit_rules_on_us_pd_newspapers.py --sample-size 9000
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any

import datasets as hf_datasets
from datasets import load_dataset
from huggingface_hub import hf_hub_download

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from slop_guard.analysis import HYPERPARAMETERS  # noqa: E402
from slop_guard.rules.registry import build_default_rules  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(
        description=(
            "Load a benchmark corpus and run fit(...) for every default rule, "
            "printing per-rule config diffs from default to fitted."
        )
    )
    parser.add_argument(
        "--dataset",
        default="PleIAs/US-PD-Newspapers",
        help="Hugging Face dataset id.",
    )
    parser.add_argument(
        "--input-mode",
        choices=["local-shard", "streaming"],
        default="local-shard",
        help=(
            "How to fetch input rows. 'local-shard' reuses one parquet shard from disk; "
            "'streaming' reads from the HF streaming iterator."
        ),
    )
    parser.add_argument(
        "--split",
        default="train",
        help="Dataset split.",
    )
    parser.add_argument(
        "--text-column",
        default="text",
        help="Name of the text column.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=9_000,
        help="Number of rows to load for fitting.",
    )
    parser.add_argument(
        "--shard-file",
        default="ak_albatross_ver01.parquet",
        help=(
            "Shard filename in the HF dataset repo. Used in local-shard mode when the "
            "file is not already present."
        ),
    )
    parser.add_argument(
        "--shard-dir",
        default="benchmark/shards",
        help="Directory where local shard parquet files are stored.",
    )
    parser.add_argument(
        "--disable-progress-bar",
        action="store_true",
        help="Disable datasets progress bars during map operations.",
    )
    parser.add_argument(
        "--log-every",
        type=int,
        default=1000,
        help="Print collection progress every N rows in streaming mode.",
    )
    return parser.parse_args()


def collect_first_n_rows(
    dataset: str,
    split: str,
    text_column: str,
    sample_size: int,
    log_every: int,
) -> tuple[hf_datasets.Dataset, int]:
    """Collect first N rows via streaming into a regular in-memory Dataset."""
    stream = load_dataset(dataset, split=split, streaming=True)

    texts: list[Any] = []
    rows_seen = 0
    for rows_seen, row in enumerate(stream.take(sample_size), start=1):
        if rows_seen == 1 and text_column not in row:
            available = ", ".join(sorted(row.keys()))
            raise KeyError(
                f"Text column '{text_column}' not found. Available: {available}"
            )
        texts.append(row.get(text_column))
        if log_every > 0 and rows_seen % log_every == 0:
            print(f"Collected {rows_seen:,} rows...", file=sys.stderr)

    return hf_datasets.Dataset.from_dict({text_column: texts}), rows_seen


def ensure_local_shard(
    dataset: str,
    shard_file: str,
    shard_dir: str,
) -> Path:
    """Return a local parquet shard path, downloading once if needed."""
    target_dir = Path(shard_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    local_path = target_dir / Path(shard_file).name
    if local_path.is_file():
        return local_path

    downloaded_path = hf_hub_download(
        repo_id=dataset,
        repo_type="dataset",
        filename=shard_file,
        local_dir=str(target_dir),
    )
    return Path(downloaded_path)


def load_first_n_from_local_shard(
    local_shard: Path,
    text_column: str,
    sample_size: int,
) -> tuple[hf_datasets.Dataset, int, int]:
    """Load first N rows from a local parquet shard."""
    dataset = load_dataset("parquet", data_files=str(local_shard), split="train")
    if text_column not in dataset.column_names:
        available = ", ".join(sorted(dataset.column_names))
        raise KeyError(
            f"Text column '{text_column}' not found in {local_shard}. "
            f"Available: {available}"
        )
    rows_available = len(dataset)
    rows_seen = min(sample_size, rows_available)
    if rows_seen == 0:
        return hf_datasets.Dataset.from_dict({text_column: []}), 0, rows_available
    return dataset.select(range(rows_seen)), rows_seen, rows_available


def corpus_from_dataset(dataset: hf_datasets.Dataset, text_column: str) -> list[str]:
    """Extract string-only corpus samples from a dataset text column."""
    raw_values = dataset[text_column]
    return [value for value in raw_values if isinstance(value, str)]


def format_rule_diff(
    before: dict[str, object],
    after: dict[str, object],
) -> tuple[int, list[str]]:
    """Return changed field count and display rows for one rule diff."""
    changed_rows: list[str] = []
    for key in sorted(set(before) | set(after)):
        before_value = before.get(key)
        after_value = after.get(key)
        if before_value == after_value:
            continue
        changed_rows.append(f"  - {key}: {before_value!r} -> {after_value!r}")
    return len(changed_rows), changed_rows


def main() -> None:
    """Load corpus, fit all rules, and print per-rule hyperparameter diffs."""
    args = parse_args()
    if args.sample_size <= 0:
        raise ValueError("--sample-size must be > 0")

    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("datasets").setLevel(logging.ERROR)
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    if args.disable_progress_bar:
        hf_datasets.disable_progress_bar()
    else:
        hf_datasets.enable_progress_bar()

    rows_seen = 0
    if args.input_mode == "local-shard":
        local_shard = ensure_local_shard(
            dataset=args.dataset,
            shard_file=args.shard_file,
            shard_dir=args.shard_dir,
        )
        print(
            (
                f"Loading first {args.sample_size:,} rows from local shard "
                f"{local_shard}..."
            ),
            file=sys.stderr,
        )
        dataset, rows_seen, rows_available = load_first_n_from_local_shard(
            local_shard=local_shard,
            text_column=args.text_column,
            sample_size=args.sample_size,
        )
        if args.sample_size > rows_seen:
            print(
                (
                    f"Requested {args.sample_size:,} rows but shard contains only "
                    f"{rows_seen:,} rows ({rows_available:,} available)."
                ),
                file=sys.stderr,
            )
    else:
        print(
            (
                f"Streaming first {args.sample_size:,} rows from "
                f"{args.dataset} ({args.split})..."
            ),
            file=sys.stderr,
        )
        dataset, rows_seen = collect_first_n_rows(
            dataset=args.dataset,
            split=args.split,
            text_column=args.text_column,
            sample_size=args.sample_size,
            log_every=args.log_every,
        )

    if len(dataset) == 0:
        raise RuntimeError("No rows were collected.")

    corpus = corpus_from_dataset(dataset, args.text_column)
    non_string_rows = rows_seen - len(corpus)
    print(
        (
            f"Loaded {rows_seen:,} rows, {len(corpus):,} string samples "
            f"({non_string_rows:,} filtered non-string rows)."
        ),
        flush=True,
    )
    if not corpus:
        raise RuntimeError("No string samples available for fit().")

    rules = build_default_rules(HYPERPARAMETERS)
    print(f"Fitting {len(rules)} rules...", flush=True)

    changed_rule_count = 0
    for index, rule in enumerate(rules, start=1):
        rule_label = f"{rule.level.value}:{rule.name}:{rule.__class__.__name__}"
        print(f"[{index}/{len(rules)}] {rule_label}", flush=True)
        before = rule.to_dict()
        started = time.perf_counter()
        rule.fit(corpus)
        fit_elapsed_s = time.perf_counter() - started
        print(f"  - fit_time_s: {fit_elapsed_s:.4f}", flush=True)
        after = rule.to_dict()
        changed_fields, rows = format_rule_diff(before, after)
        if changed_fields == 0:
            print("  - (no config changes)", flush=True)
            continue
        changed_rule_count += 1
        print(f"  - changed_fields: {changed_fields}", flush=True)
        for row in rows:
            print(row, flush=True)

    print(
        (
            f"Done. {changed_rule_count}/{len(rules)} rules changed at least one "
            "hyperparameter."
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
