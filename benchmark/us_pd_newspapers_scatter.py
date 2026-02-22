# /// script
# requires-python = ">=3.10"
# dependencies = ["datasets", "huggingface_hub", "matplotlib", "mcp", "seaborn"]
# ///
"""Benchmark slop-guard and render a score-vs-length scatter plot.

Example:
    uv run benchmark/us_pd_newspapers_scatter.py --sample-size 100000
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import statistics
import sys
import urllib.request
from pathlib import Path
from typing import Any

import datasets as hf_datasets
from datasets import load_dataset
from huggingface_hub import hf_hub_download
import matplotlib
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
            "and write a score-vs-length scatter plot."
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
        "--scatter-png",
        default="",
        help=(
            "Explicit output path for scatter PNG. Defaults to "
            "<output-dir>/score_vs_length_scatter.png."
        ),
    )
    parser.add_argument(
        "--plot-from-samples-csv",
        default="",
        help=(
            "Shortcut mode: skip scoring and re-render scatter from an existing "
            "score_length_samples.csv."
        ),
    )
    parser.add_argument(
        "--plot-from-summary-json",
        default="",
        help=(
            "Optional summary JSON path for title metadata in shortcut mode. "
            "Defaults to sibling scatter_summary.json or summary.json next to "
            "--plot-from-samples-csv if present."
        ),
    )
    parser.add_argument(
        "--save-scores",
        action="store_true",
        help="Also write raw per-document scores to a histogram-compatible CSV.",
    )
    return parser.parse_args()


def build_scatter_title(
    dataset: str,
    split: str,
    sample_size_scored: int | None,
) -> str:
    """Build a standard scatter title string."""
    normalized_split = split.capitalize()
    headline = "Slop-Guard Score vs Length"
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


def scatter_white_variant_path(scatter_png: Path) -> Path:
    """Return the white-background companion PNG path."""
    return scatter_png.with_name(f"{scatter_png.stem}.white{scatter_png.suffix}")


def save_scatter_png_variants(fig: plt.Figure, scatter_png: Path) -> tuple[Path, Path]:
    """Save transparent and white-background PNG variants."""
    output_dpi = 320
    scatter_png.parent.mkdir(parents=True, exist_ok=True)
    white_png = scatter_white_variant_path(scatter_png)
    fig.savefig(scatter_png, dpi=output_dpi, transparent=True)
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
    return scatter_png, white_png


def read_samples_csv(path: Path) -> tuple[list[float], list[float]]:
    """Load `(length, score)` points from CSV."""
    lengths: list[float] = []
    scores: list[float] = []

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise RuntimeError(f"CSV has no header: {path}")

        length_field: str | None = None
        for candidate in ("length", "word_count"):
            if candidate in reader.fieldnames:
                length_field = candidate
                break

        if length_field is None or "score" not in reader.fieldnames:
            raise RuntimeError(
                f"CSV must include score and length/word_count columns: {path}"
            )

        for row in reader:
            score_raw = row.get("score")
            length_raw = row.get(length_field)
            if not score_raw or not length_raw:
                continue
            try:
                scores.append(float(score_raw))
                lengths.append(float(length_raw))
            except ValueError:
                continue

    if not lengths:
        raise RuntimeError(f"No scatter samples found in {path}")
    return lengths, scores


def fit_linear_regression(
    lengths: list[float], scores: list[float]
) -> tuple[float, float, float | None]:
    """Fit `score ~ slope * length + intercept` and compute Pearson correlation."""
    if len(lengths) != len(scores):
        raise ValueError("Lengths and scores must have equal lengths")
    if not lengths:
        raise ValueError("Lengths and scores are empty")

    if len(lengths) == 1:
        return 0.0, float(scores[0]), None

    try:
        fit = statistics.linear_regression(lengths, scores)
        slope = float(fit.slope)
        intercept = float(fit.intercept)
    except statistics.StatisticsError:
        slope = 0.0
        intercept = float(statistics.fmean(scores))

    try:
        corr = float(statistics.correlation(lengths, scores))
    except statistics.StatisticsError:
        corr = None

    return slope, intercept, corr


def plot_scatter_from_samples(
    scatter_png: Path,
    title: str,
    lengths: list[float],
    scores: list[float],
) -> tuple[Path, Path, float, float, float | None]:
    """Render a scatter image from raw `(length, score)` points."""
    if len(lengths) != len(scores):
        raise ValueError("Scatter arrays must have equal lengths")
    if not lengths:
        raise ValueError("Scatter samples are empty")

    slope, intercept, corr = fit_linear_regression(lengths, scores)
    x_min = min(lengths)
    x_max = max(lengths)
    if x_min == x_max:
        x_min = x_min - 0.5
        x_max = x_max + 0.5

    sns.set_theme(style="whitegrid")
    configure_plot_typography()
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("white")

    sns.scatterplot(
        x=lengths,
        y=scores,
        s=13,
        alpha=0.34,
        color="#4C72B0",
        edgecolor=None,
        linewidth=0.0,
        ax=ax,
    )
    ax.plot(
        [x_min, x_max],
        [slope * x_min + intercept, slope * x_max + intercept],
        color="#C33C54",
        linewidth=2.2,
        zorder=4,
    )

    ax.set_xlim(left=0)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Length (word count)")
    ax.set_ylabel("Score")

    ax.text(
        0.02,
        0.02,
        title,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
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

    corr_label = "Pearson r = n/a (constant input)" if corr is None else f"Pearson r = {corr:.3f}"
    line_label = f"y = {slope:.4f}x + {intercept:.3f}"
    ax.text(
        0.98,
        0.02,
        f"{corr_label}\n{line_label}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        multialignment="right",
        fontsize=11,
        bbox={
            "boxstyle": "round,pad=0.35,rounding_size=0.25",
            "facecolor": "white",
            "edgecolor": "#9AA4B2",
            "linewidth": 1.0,
            "alpha": 0.96,
        },
        zorder=5,
    )

    ax.grid(axis="both", color="#E6E9EF", linewidth=0.9)
    fig.subplots_adjust(left=0.11, right=0.985, bottom=0.12, top=0.95)
    transparent_png, white_png = save_scatter_png_variants(fig, scatter_png)
    plt.close(fig)
    return transparent_png, white_png, slope, intercept, corr


def score_text_value(text: Any) -> dict[str, Any]:
    """Score one text cell and return compact fields for aggregation."""
    if not isinstance(text, str):
        return {"score": None, "length": None, "band": None}

    result = _analyze(text, HYPERPARAMETERS)
    return {
        "score": int(result["score"]),
        "length": int(result["word_count"]),
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


def resolve_plot_mode_summary(
    requested_path: str,
    samples_csv_path: Path,
) -> dict[str, Any] | None:
    """Load optional summary metadata when plotting from existing sample CSV."""
    candidates: list[Path] = []
    if requested_path:
        candidates.append(Path(requested_path))
    else:
        candidates.extend(
            [
                samples_csv_path.parent / "scatter_summary.json",
                samples_csv_path.parent / "summary.json",
            ]
        )

    for candidate in candidates:
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return None


def main() -> None:
    """Run the benchmark and write scatter + summary artifacts."""
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
    scatter_png = (
        Path(args.scatter_png)
        if args.scatter_png
        else (output_dir / "score_vs_length_scatter.png")
    )
    scatter_white_png = scatter_white_variant_path(scatter_png)

    if args.plot_from_samples_csv:
        samples_csv_path = Path(args.plot_from_samples_csv)
        if not samples_csv_path.is_file():
            raise FileNotFoundError(
                f"--plot-from-samples-csv not found: {samples_csv_path}"
            )

        summary_payload = resolve_plot_mode_summary(
            requested_path=args.plot_from_summary_json,
            samples_csv_path=samples_csv_path,
        )
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

        lengths, scores = read_samples_csv(samples_csv_path)
        transparent_png, white_png, slope, intercept, corr = plot_scatter_from_samples(
            scatter_png=scatter_png,
            title=build_scatter_title(dataset_name, split_name, sample_size_scored),
            lengths=lengths,
            scores=scores,
        )
        print(
            json.dumps(
                {
                    "mode": "plot_from_samples_csv",
                    "scatter_samples_csv": str(samples_csv_path),
                    "scatter_png": str(transparent_png),
                    "scatter_white_png": str(white_png),
                    "dataset": dataset_name,
                    "split": split_name,
                    "sample_size_scored": sample_size_scored,
                    "correlation": corr,
                    "regression_slope": slope,
                    "regression_intercept": intercept,
                },
                indent=2,
            )
        )
        return

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
        raise RuntimeError("No rows were collected from the input source.")

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

    scores: list[float] = []
    lengths: list[float] = []
    scored_rows: list[tuple[float, float, str]] = []
    band_counts = {"clean": 0, "light": 0, "moderate": 0, "heavy": 0, "saturated": 0}
    for score, length, band in zip(
        scored_dataset["score"],
        scored_dataset["length"],
        scored_dataset["band"],
    ):
        if score is None or length is None or band is None:
            continue
        score_f = float(score)
        length_f = float(length)
        band_s = str(band)
        scores.append(score_f)
        lengths.append(length_f)
        scored_rows.append((score_f, length_f, band_s))
        if band_s in band_counts:
            band_counts[band_s] += 1

    if not scores:
        raise RuntimeError("No scores produced.")

    scatter_png, scatter_white_png, slope, intercept, corr = plot_scatter_from_samples(
        scatter_png=scatter_png,
        title=build_scatter_title(args.dataset, args.split, len(scores)),
        lengths=lengths,
        scores=scores,
    )

    samples_csv = output_dir / "score_length_samples.csv"
    with samples_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["index", "score", "length", "band"])
        for i, (score, length, band) in enumerate(scored_rows, start=1):
            writer.writerow([i, f"{score:.0f}", f"{length:.0f}", band])

    if args.save_scores:
        score_csv = output_dir / "score_samples.csv"
        with score_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["index", "score", "word_count"])
            for i, (score, length, _band) in enumerate(scored_rows, start=1):
                writer.writerow([i, int(round(score)), int(round(length))])

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
        "mean_score": round(statistics.fmean(scores), 3),
        "median_score": round(statistics.median(scores), 3),
        "mean_length": round(statistics.fmean(lengths), 3),
        "median_length": round(statistics.median(lengths), 3),
        "min_score": round(min(scores), 3),
        "max_score": round(max(scores), 3),
        "min_length": round(min(lengths), 3),
        "max_length": round(max(lengths), 3),
        "band_counts": band_counts,
        "correlation": corr,
        "regression_slope": slope,
        "regression_intercept": intercept,
        "artifacts": {
            "scatter_png": str(scatter_png),
            "scatter_white_png": str(scatter_white_png),
            "scatter_samples_csv": str(samples_csv),
        },
    }

    summary_json = output_dir / "scatter_summary.json"
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
