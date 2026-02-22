# /// script
# requires-python = ">=3.10"
# dependencies = ["datasets", "huggingface_hub", "matplotlib", "mcp", "seaborn"]
# ///
"""Benchmark slop-guard on Hugging Face corpora.

Example:
    uv run benchmark/us_pd_newspapers_histogram.py --sample-size 100000
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import os
import statistics
import sys
import urllib.request
from pathlib import Path
from typing import Any

import matplotlib
import datasets as hf_datasets
from datasets import load_dataset
from huggingface_hub import hf_hub_download
import seaborn as sns

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from slop_guard import HYPERPARAMETERS, _analyze  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    default_num_proc = max(1, (os.cpu_count() or 1) - 1)

    parser = argparse.ArgumentParser(
        description=(
            "Sample texts from a Hugging Face dataset, score them with slop-guard, "
            "and write a histogram."
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
        default=100_000,
        help="Number of rows to score.",
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
        "--bins",
        type=int,
        default=50,
        help="Number of histogram bins between 0 and 100.",
    )
    parser.add_argument(
        "--num-proc",
        type=int,
        default=default_num_proc,
        help="Parallel worker processes for Dataset.map().",
    )
    parser.add_argument(
        "--disable-progress-bar",
        action="store_true",
        help="Disable datasets progress bars during map operations.",
    )
    parser.add_argument(
        "--log-every",
        type=int,
        default=0,
        help="Reserved for non-map flows; ignored when using Dataset.map().",
    )
    parser.add_argument(
        "--output-dir",
        default="benchmark/output",
        help="Directory for outputs.",
    )
    parser.add_argument(
        "--histogram-png",
        default="",
        help=(
            "Explicit output path for histogram PNG. Defaults to "
            "<output-dir>/score_histogram.png."
        ),
    )
    parser.add_argument(
        "--plot-from-bins-csv",
        default="",
        help=(
            "Shortcut mode: skip scoring and re-render histogram from an existing "
            "score_histogram_bins.csv."
        ),
    )
    parser.add_argument(
        "--plot-from-summary-json",
        default="",
        help=(
            "Optional summary JSON path for title metadata in shortcut mode. "
            "Defaults to sibling summary.json next to --plot-from-bins-csv if present."
        ),
    )
    parser.add_argument(
        "--save-scores",
        action="store_true",
        help="Write raw per-document scores to a CSV.",
    )
    return parser.parse_args()


def percentile(sorted_values: list[float], pct: float) -> float:
    """Compute a percentile with linear interpolation."""
    if not sorted_values:
        raise ValueError("percentile() requires non-empty values")
    if pct <= 0:
        return sorted_values[0]
    if pct >= 100:
        return sorted_values[-1]
    rank = (len(sorted_values) - 1) * (pct / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_values[low]
    weight = rank - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


def build_histogram_title(
    dataset: str,
    split: str,
    sample_size_scored: int | None,
) -> str:
    """Build a standard histogram title string."""
    normalized_split = split.capitalize()
    headline = "Slop-Guard Score Distribution"
    if sample_size_scored is None:
        return f"{headline}\n{dataset} ({normalized_split})"
    return (
        f"{headline}\n"
        f"{dataset} ({normalized_split})\n"
        f"$N = {sample_size_scored}$"
    )


def ensure_literata_font() -> str:
    """Ensure Literata is available and return the concrete font family name."""
    try:
        font_manager.findfont("Literata", fallback_to_default=False)
        return "Literata"
    except Exception:
        pass

    font_dir = REPO_ROOT / "benchmark" / "assets" / "fonts"
    font_dir.mkdir(parents=True, exist_ok=True)
    font_path = font_dir / "Literata-Variable.ttf"
    if (not font_path.is_file()) or font_path.stat().st_size == 0:
        try:
            urllib.request.urlretrieve(
                "https://raw.githubusercontent.com/google/fonts/main/ofl/literata/Literata%5Bopsz%2Cwght%5D.ttf",
                font_path,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            raise RuntimeError(
                "Could not download Literata font. Install Literata and rerun."
            ) from exc

    font_manager.fontManager.addfont(str(font_path))
    literata_name = font_manager.FontProperties(fname=str(font_path)).get_name()
    font_manager.findfont(literata_name, fallback_to_default=False)
    return literata_name


def configure_plot_typography() -> None:
    """Configure plotting typography, requiring the Literata font."""
    literata_name = ensure_literata_font()

    plt.rcParams.update(
        {
            "font.family": literata_name,
            "font.serif": [literata_name],
            "mathtext.fontset": "stix",
            "axes.titlesize": 16,
            "axes.labelsize": 13,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "axes.titleweight": "semibold",
            "axes.labelweight": "medium",
        }
    )


def histogram_white_variant_path(histogram_png: Path) -> Path:
    """Return the white-background companion PNG path."""
    return histogram_png.with_name(f"{histogram_png.stem}.white{histogram_png.suffix}")


def save_histogram_png_variants(fig: plt.Figure, histogram_png: Path) -> tuple[Path, Path]:
    """Save transparent and white-background PNG variants."""
    output_dpi = 320
    histogram_png.parent.mkdir(parents=True, exist_ok=True)
    white_png = histogram_white_variant_path(histogram_png)
    fig.savefig(histogram_png, dpi=output_dpi, transparent=True)
    original_facecolor = fig.patch.get_facecolor()
    original_edgecolor = fig.patch.get_edgecolor()
    original_alpha = fig.patch.get_alpha()
    fig.patch.set_facecolor("white")
    fig.patch.set_edgecolor("white")
    fig.patch.set_alpha(1.0)
    fig.savefig(
        white_png,
        dpi=output_dpi,
        transparent=False,
        facecolor="white",
        edgecolor="white",
    )
    fig.patch.set_facecolor(original_facecolor)
    fig.patch.set_edgecolor(original_edgecolor)
    fig.patch.set_alpha(original_alpha)
    return histogram_png, white_png


def read_histogram_bins_csv(
    path: Path,
) -> tuple[list[float], list[float], list[float]]:
    """Load histogram bins from CSV."""
    bin_starts: list[float] = []
    bin_ends: list[float] = []
    counts: list[float] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bin_starts.append(float(row["bin_start"]))
            bin_ends.append(float(row["bin_end"]))
            counts.append(float(row["count"]))
    if not bin_starts:
        raise RuntimeError(f"No histogram bins found in {path}")
    return bin_starts, bin_ends, counts


def plot_histogram_from_bins(
    histogram_png: Path,
    title: str,
    bin_starts: list[float],
    bin_ends: list[float],
    counts: list[float],
) -> tuple[Path, Path]:
    """Render a histogram image from pre-aggregated bin stats."""
    if not (len(bin_starts) == len(bin_ends) == len(counts)):
        raise ValueError("Histogram bin arrays must have equal lengths")
    if not bin_starts:
        raise ValueError("Histogram bins are empty")

    bin_edges = [*bin_starts, bin_ends[-1]]
    bin_centers = [(left + right) / 2.0 for left, right in zip(bin_starts, bin_ends)]

    sns.set_theme(style="whitegrid")
    configure_plot_typography()
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("white")

    sns.histplot(
        x=bin_centers,
        weights=counts,
        bins=bin_edges,
        stat="count",
        element="bars",
        fill=True,
        color="#4C72B0",
        edgecolor="#1F2937",
        linewidth=0.7,
        ax=ax,
    )

    ax.set_xlim(bin_edges[0], bin_edges[-1])
    ax.set_xlabel("Score")
    ax.set_ylabel("Count")
    ax.text(
        0.02,
        0.98,
        title,
        transform=ax.transAxes,
        ha="left",
        va="top",
        multialignment="left",
        fontsize=13,
        bbox={
            "boxstyle": "round,pad=0.35,rounding_size=0.25",
            "facecolor": "white",
            "edgecolor": "#9AA4B2",
            "linewidth": 1.0,
            "alpha": 0.96,
        },
        zorder=5,
    )

    ax.grid(axis="y", color="#E6E9EF", linewidth=0.9)
    ax.grid(axis="x", visible=False)
    fig.subplots_adjust(left=0.11, right=0.985, bottom=0.12, top=0.95)
    transparent_png, white_png = save_histogram_png_variants(fig, histogram_png)
    plt.close(fig)
    return transparent_png, white_png


def score_text_value(text: Any) -> dict[str, Any]:
    """Score one text cell and return compact fields for aggregation."""
    if not isinstance(text, str):
        return {"score": None, "word_count": None, "band": None}

    result = _analyze(text, HYPERPARAMETERS)
    return {
        "score": int(result["score"]),
        "word_count": int(result["word_count"]),
        "band": str(result["band"]),
    }


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


def main() -> None:
    """Run the benchmark and write histogram + summary artifacts."""
    args = parse_args()
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("datasets").setLevel(logging.ERROR)
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    if args.disable_progress_bar:
        hf_datasets.disable_progress_bar()
    else:
        hf_datasets.enable_progress_bar()

    if args.sample_size <= 0:
        raise ValueError("--sample-size must be > 0")
    if args.num_proc <= 0:
        raise ValueError("--num-proc must be > 0")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    histogram_png = Path(args.histogram_png) if args.histogram_png else (output_dir / "score_histogram.png")
    histogram_white_png = histogram_white_variant_path(histogram_png)

    if args.plot_from_bins_csv:
        bins_csv_path = Path(args.plot_from_bins_csv)
        if not bins_csv_path.is_file():
            raise FileNotFoundError(f"--plot-from-bins-csv not found: {bins_csv_path}")

        summary_payload: dict[str, Any] | None = None
        if args.plot_from_summary_json:
            summary_path = Path(args.plot_from_summary_json)
            if summary_path.is_file():
                summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
        else:
            default_summary_path = bins_csv_path.parent / "summary.json"
            if default_summary_path.is_file():
                summary_payload = json.loads(default_summary_path.read_text(encoding="utf-8"))

        dataset_name = (
            str(summary_payload.get("dataset"))
            if summary_payload and summary_payload.get("dataset")
            else args.dataset
        )
        split_name = (
            str(summary_payload.get("split"))
            if summary_payload and summary_payload.get("split")
            else args.split
        )
        sample_size_scored = None
        if summary_payload and "sample_size_scored" in summary_payload:
            sample_size_scored = int(summary_payload["sample_size_scored"])

        bin_starts, bin_ends, counts = read_histogram_bins_csv(bins_csv_path)
        transparent_png, white_png = plot_histogram_from_bins(
            histogram_png=histogram_png,
            title=build_histogram_title(dataset_name, split_name, sample_size_scored),
            bin_starts=bin_starts,
            bin_ends=bin_ends,
            counts=counts,
        )
        print(
            json.dumps(
                {
                    "mode": "plot_from_bins_csv",
                    "histogram_bins_csv": str(bins_csv_path),
                    "histogram_png": str(transparent_png),
                    "histogram_white_png": str(white_png),
                    "dataset": dataset_name,
                    "split": split_name,
                    "sample_size_scored": sample_size_scored,
                },
                indent=2,
            )
        )
        return

    band_counts = {"clean": 0, "light": 0, "moderate": 0, "heavy": 0, "saturated": 0}
    local_shard_path: Path | None = None
    rows_available_in_local_shard: int | None = None
    if args.input_mode == "local-shard":
        local_shard_path = ensure_local_shard(
            dataset=args.dataset,
            shard_file=args.shard_file,
            shard_dir=args.shard_dir,
        )
        print(
            (
                f"Loading first {args.sample_size:,} rows from local shard "
                f"{local_shard_path}..."
            ),
            file=sys.stderr,
        )
        dataset, rows_seen, rows_available_in_local_shard = load_first_n_from_local_shard(
            local_shard=local_shard_path,
            text_column=args.text_column,
            sample_size=args.sample_size,
        )
        if args.sample_size > rows_seen:
            print(
                (
                    f"Requested {args.sample_size:,} rows but shard contains only "
                    f"{rows_seen:,} rows."
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
        raise RuntimeError("No rows were collected from the stream.")

    effective_num_proc = min(args.num_proc, len(dataset))
    map_num_proc = effective_num_proc if effective_num_proc > 1 else None
    print(
        f"Scoring {len(dataset):,} rows with num_proc={effective_num_proc}...",
        file=sys.stderr,
    )
    scored_dataset = dataset.map(
        score_text_value,
        input_columns=[args.text_column],
        remove_columns=dataset.column_names,
        num_proc=map_num_proc,
        load_from_cache_file=False,
        desc="Scoring rows with slop-guard",
    )

    scores: list[int] = []
    word_counts: list[int] = []
    scored_rows: list[tuple[int, int, str]] = []
    for score, word_count, band in zip(
        scored_dataset["score"],
        scored_dataset["word_count"],
        scored_dataset["band"],
    ):
        if score is None or word_count is None or band is None:
            continue
        score_i = int(score)
        word_count_i = int(word_count)
        band_s = str(band)
        scores.append(score_i)
        word_counts.append(word_count_i)
        scored_rows.append((score_i, word_count_i, band_s))
        if band_s in band_counts:
            band_counts[band_s] += 1

    if not scores:
        raise RuntimeError("No scores produced.")

    # Histogram bin stats from raw scores.
    bin_edges = [i * (100.0 / args.bins) for i in range(args.bins + 1)]
    counts = [0] * args.bins
    for score in scores:
        if score >= 100:
            bin_index = args.bins - 1
        elif score <= 0:
            bin_index = 0
        else:
            bin_index = int((score / 100.0) * args.bins)
            if bin_index >= args.bins:
                bin_index = args.bins - 1
        counts[bin_index] += 1

    bin_starts = bin_edges[:-1]
    bin_ends = bin_edges[1:]
    histogram_png, histogram_white_png = plot_histogram_from_bins(
        histogram_png=histogram_png,
        title=build_histogram_title(args.dataset, args.split, len(scores)),
        bin_starts=bin_starts,
        bin_ends=bin_ends,
        counts=[float(x) for x in counts],
    )

    histogram_csv = output_dir / "score_histogram_bins.csv"
    with histogram_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["bin_start", "bin_end", "count"])
        for left, right, count in zip(bin_starts, bin_ends, counts):
            writer.writerow([float(left), float(right), int(count)])

    if args.save_scores:
        score_csv = output_dir / "score_samples.csv"
        with score_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["index", "score", "word_count"])
            for i, (score, words, _band) in enumerate(scored_rows, start=1):
                writer.writerow([i, score, words])

    sorted_scores = sorted(float(x) for x in scores)
    summary = {
        "dataset": args.dataset,
        "input_mode": args.input_mode,
        "split": args.split,
        "text_column": args.text_column,
        "local_shard_path": str(local_shard_path) if local_shard_path else None,
        "local_shard_file": args.shard_file if args.input_mode == "local-shard" else None,
        "rows_available_in_local_shard": rows_available_in_local_shard,
        "sample_size_requested": args.sample_size,
        "sample_size_seen": rows_seen,
        "sample_size_loaded": len(dataset),
        "sample_size_scored": len(scores),
        "sampling_method": (
            "first_n_local_shard_rows_then_parallel_map"
            if args.input_mode == "local-shard"
            else "first_n_streaming_rows_then_parallel_map"
        ),
        "num_proc_requested": args.num_proc,
        "num_proc_used": effective_num_proc,
        "progress_bar_enabled": not args.disable_progress_bar,
        "bins": args.bins,
        "mean_score": round(statistics.fmean(sorted_scores), 3),
        "median_score": round(statistics.median(sorted_scores), 3),
        "min_score": int(min(scores)),
        "max_score": int(max(scores)),
        "p10_score": round(percentile(sorted_scores, 10), 3),
        "p25_score": round(percentile(sorted_scores, 25), 3),
        "p75_score": round(percentile(sorted_scores, 75), 3),
        "p90_score": round(percentile(sorted_scores, 90), 3),
        "mean_word_count": round(statistics.fmean(word_counts), 3),
        "band_counts": band_counts,
        "artifacts": {
            "histogram_png": str(histogram_png),
            "histogram_white_png": str(histogram_white_png),
            "histogram_bins_csv": str(histogram_csv),
        },
    }

    summary_json = output_dir / "summary.json"
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
