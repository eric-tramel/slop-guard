# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib", "pandas", "seaborn"]
# ///
"""Render a compute-time chart from JSONL benchmark output.

Example:
    uv run benchmark/chart.py \
        --input benchmark/output/rule_compute_time.jsonl \
        --output benchmark/output/rule_compute_time.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TypeAlias

import matplotlib
import pandas as pd
import seaborn as sns

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

JsonRow: TypeAlias = dict[str, object]

_LEVEL_PALETTE = {
    "word": "#1b9e77",
    "sentence": "#d95f02",
    "paragraph": "#7570b3",
    "passage": "#66a61e",
}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Read per-rule timing JSONL and render a line chart where each line "
            "is a rule and hue corresponds to rule level."
        )
    )
    parser.add_argument(
        "--input",
        default="benchmark/output/rule_compute_time.jsonl",
        help="Input JSONL path from benchmark/compute-time.py.",
    )
    parser.add_argument(
        "--output",
        default="benchmark/output/rule_compute_time.png",
        help="Output chart PNG path.",
    )
    parser.add_argument(
        "--title",
        default="Rule Compute Time by Text Length",
        help="Chart title.",
    )
    parser.add_argument(
        "--x-scale",
        choices=("linear", "log"),
        default="linear",
        help="Scale used for the text-length axis.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=240,
        help="Output image resolution (dots per inch).",
    )
    parser.add_argument(
        "--width",
        type=float,
        default=12.0,
        help="Figure width in inches.",
    )
    parser.add_argument(
        "--height",
        type=float,
        default=7.0,
        help="Figure height in inches.",
    )
    parser.add_argument(
        "--annotate-top-n",
        type=int,
        default=8,
        help=(
            "Annotate the slowest N rule curves at the maximum text length. "
            "Use 0 to disable annotations."
        ),
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> pd.DataFrame:
    """Load JSONL benchmark rows into a typed DataFrame."""
    if not path.is_file():
        raise FileNotFoundError(f"Input file does not exist: {path}")

    rows: list[JsonRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON at {path}:{line_number}: {exc.msg}"
                ) from exc
            rows.append(payload)

    if not rows:
        raise ValueError(f"No rows found in input JSONL: {path}")

    frame = pd.DataFrame(rows)
    required = {"rule", "level", "word_count", "time_ms"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            f"Input JSONL is missing required column(s): {', '.join(sorted(missing))}"
        )

    frame["word_count"] = pd.to_numeric(frame["word_count"])
    frame["time_ms"] = pd.to_numeric(frame["time_ms"])
    frame["rule"] = frame["rule"].astype(str)
    frame["level"] = frame["level"].astype(str)
    return frame


def aggregate_for_plot(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate timing runs into one mean point per rule/length pair."""
    grouped = (
        frame.groupby(["rule", "level", "word_count"], as_index=False)["time_ms"]
        .mean()
        .sort_values(["level", "rule", "word_count"])
    )
    return grouped


def _annotation_offsets(count: int, step: int = 12) -> list[int]:
    """Build alternating y-offsets in points to reduce label overlap."""
    if count <= 0:
        return []
    offsets = [0]
    for idx in range(1, count):
        magnitude = ((idx + 1) // 2) * step
        sign = 1 if idx % 2 else -1
        offsets.append(sign * magnitude)
    return offsets


def annotate_slowest_curves(
    *,
    axis: plt.Axes,
    frame: pd.DataFrame,
    x_scale: str,
    top_n: int,
) -> pd.DataFrame:
    """Annotate the slowest rule curves at the longest measured input length."""
    if top_n <= 0:
        return frame.iloc[0:0]

    max_words = frame["word_count"].max()
    endpoints = frame[frame["word_count"] == max_words].copy()
    if endpoints.empty:
        return endpoints

    ranked = endpoints.sort_values("time_ms", ascending=False).head(top_n)
    offsets = _annotation_offsets(len(ranked))
    x_min, x_max = axis.get_xlim()
    growth = 1.16 if x_scale == "log" else 1.06
    axis.set_xlim(x_min, x_max * growth)

    for (idx, (_, row)) in enumerate(ranked.iterrows()):
        level = str(row["level"])
        color = _LEVEL_PALETTE.get(level, "#333333")
        label = f"{row['rule']} ({row['time_ms']:.2f} ms)"
        axis.annotate(
            label,
            xy=(float(row["word_count"]), float(row["time_ms"])),
            xytext=(10, offsets[idx]),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=8,
            color=color,
            bbox={
                "boxstyle": "round,pad=0.2",
                "facecolor": "white",
                "edgecolor": color,
                "alpha": 0.75,
                "linewidth": 0.8,
            },
            arrowprops={
                "arrowstyle": "-",
                "linewidth": 0.8,
                "color": color,
                "alpha": 0.8,
            },
            annotation_clip=False,
        )
    return ranked


def render_chart(
    *,
    frame: pd.DataFrame,
    output: Path,
    title: str,
    x_scale: str,
    dpi: int,
    width: float,
    height: float,
    annotate_top_n: int,
) -> None:
    """Render and save a Seaborn line chart."""
    sns.set_theme(style="whitegrid")
    figure, axis = plt.subplots(figsize=(width, height))
    sns.lineplot(
        data=frame,
        x="word_count",
        y="time_ms",
        hue="level",
        units="rule",
        estimator=None,
        linewidth=1.2,
        alpha=0.85,
        palette=_LEVEL_PALETTE,
        ax=axis,
    )
    if x_scale == "log":
        axis.set_xscale("log")
    axis.set_xlabel("Text length (words)")
    axis.set_ylabel("Compute time (ms)")
    axis.set_title(title)
    annotate_slowest_curves(
        axis=axis,
        frame=frame,
        x_scale=x_scale,
        top_n=annotate_top_n,
    )
    axis.legend(title="Rule level", loc="upper left", frameon=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(output, dpi=dpi)
    plt.close(figure)


def main() -> None:
    """Load benchmark data, render chart, and write PNG output."""
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    raw = load_jsonl(input_path)
    plot_frame = aggregate_for_plot(raw)
    render_chart(
        frame=plot_frame,
        output=output_path,
        title=args.title,
        x_scale=args.x_scale,
        dpi=args.dpi,
        width=args.width,
        height=args.height,
        annotate_top_n=args.annotate_top_n,
    )
    print(
        "Chart written:",
        f"{output_path}",
        f"({len(plot_frame)} aggregated points from {len(raw)} rows)",
    )


if __name__ == "__main__":
    main()
