# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Statistical analysis and reporting for evaluation results.

Reads JSONL trial results and computes aggregate statistics, per-genre
breakdowns, and paired comparisons between control and treatment conditions.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

TrialRecord: TypeAlias = dict[str, object]
GroupedRecords: TypeAlias = dict[str, list[TrialRecord]]


@dataclass(frozen=True)
class PairedComparison:
    """Statistical summary of control vs. treatment for one metric."""

    metric: str
    control_mean: float
    treatment_mean: float
    delta: float
    relative_change_pct: float
    n_pairs: int
    cohens_d: float

    def to_dict(self) -> dict[str, object]:
        """Serialize for JSON output."""
        return {
            "metric": self.metric,
            "control_mean": round(self.control_mean, 3),
            "treatment_mean": round(self.treatment_mean, 3),
            "delta": round(self.delta, 3),
            "relative_change_pct": round(self.relative_change_pct, 2),
            "n_pairs": self.n_pairs,
            "cohens_d": round(self.cohens_d, 3),
        }


@dataclass(frozen=True)
class ConvergenceStats:
    """Aggregate statistics on the treatment revision loop."""

    mean_revisions: float
    convergence_rate: float
    mean_initial_score: float
    mean_final_score: float
    mean_score_lift: float

    def to_dict(self) -> dict[str, object]:
        """Serialize for JSON output."""
        return {
            "mean_revisions": round(self.mean_revisions, 2),
            "convergence_rate_pct": round(self.convergence_rate * 100, 1),
            "mean_initial_score": round(self.mean_initial_score, 1),
            "mean_final_score": round(self.mean_final_score, 1),
            "mean_score_lift": round(self.mean_score_lift, 1),
        }


@dataclass(frozen=True)
class GamingDetection:
    """Metrics for detecting if the agent games slop-guard without real improvement.

    If slop-guard score rises but external quality metrics degrade (e.g.,
    lexical diversity drops, readability worsens), the agent may be pattern-
    matching against the linter rather than genuinely improving prose.
    """

    slop_score_delta: float
    type_token_ratio_delta: float
    hapax_ratio_delta: float
    sentence_length_cv_delta: float
    flesch_kincaid_delta: float
    gaming_flag: bool

    def to_dict(self) -> dict[str, object]:
        """Serialize for JSON output."""
        return {
            "slop_score_delta": round(self.slop_score_delta, 2),
            "type_token_ratio_delta": round(self.type_token_ratio_delta, 4),
            "hapax_ratio_delta": round(self.hapax_ratio_delta, 4),
            "sentence_length_cv_delta": round(self.sentence_length_cv_delta, 4),
            "flesch_kincaid_delta": round(self.flesch_kincaid_delta, 2),
            "gaming_flag": self.gaming_flag,
        }


def load_results(path: Path) -> list[TrialRecord]:
    """Load JSONL trial results from disk."""
    records: list[TrialRecord] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _mean(values: list[float]) -> float:
    """Compute arithmetic mean, returning 0.0 for empty lists."""
    return sum(values) / len(values) if values else 0.0


def _stddev(values: list[float]) -> float:
    """Compute population standard deviation."""
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / len(values))


def _cohens_d(control: list[float], treatment: list[float]) -> float:
    """Compute Cohen's d effect size for paired samples."""
    if not control or not treatment:
        return 0.0
    deltas = [t - c for c, t in zip(control, treatment)]
    mean_delta = _mean(deltas)
    sd = _stddev(deltas)
    return mean_delta / sd if sd > 0 else 0.0


def _group_by_task(records: list[TrialRecord]) -> GroupedRecords:
    """Group records by task_id."""
    groups: GroupedRecords = defaultdict(list)
    for record in records:
        task_id = str(record.get("task_id", ""))
        groups[task_id].append(record)
    return dict(groups)


def _extract_metric(
    record: TrialRecord, metric: str, prefix: str = "final"
) -> float:
    """Extract a metric value from a trial record.

    Checks top-level keys first, then falls back to quality_metrics sub-dict.
    """
    key = f"{prefix}_{metric}" if prefix else metric
    if key in record:
        return float(record[key])  # type: ignore[arg-type]

    quality_key = f"{prefix}_quality_metrics"
    quality = record.get(quality_key, {})
    if isinstance(quality, dict) and metric in quality:
        return float(quality[metric])

    return 0.0


def compute_paired_comparisons(
    records: list[TrialRecord],
    metrics: tuple[str, ...] = (
        "score",
        "type_token_ratio",
        "hapax_ratio",
        "sentence_length_cv",
        "flesch_kincaid_grade",
        "gunning_fog_index",
        "unique_word_pct",
        "avg_sentence_length",
        "paragraph_length_cv",
    ),
) -> list[PairedComparison]:
    """Compute paired control-vs-treatment comparisons for each metric.

    Args:
        records: All trial records (control and treatment intermixed).
        metrics: Metric names to compare.

    Returns:
        One PairedComparison per metric.
    """
    groups = _group_by_task(records)
    comparisons: list[PairedComparison] = []

    for metric in metrics:
        control_vals: list[float] = []
        treatment_vals: list[float] = []

        for task_records in groups.values():
            ctrl = [r for r in task_records if r.get("condition") == "control"]
            treat = [r for r in task_records if r.get("condition") == "treatment"]
            if not ctrl or not treat:
                continue
            control_vals.append(_extract_metric(ctrl[0], metric))
            treatment_vals.append(_extract_metric(treat[0], metric))

        if not control_vals:
            continue

        ctrl_mean = _mean(control_vals)
        treat_mean = _mean(treatment_vals)
        delta = treat_mean - ctrl_mean
        relative_pct = (delta / ctrl_mean * 100) if ctrl_mean != 0 else 0.0

        comparisons.append(PairedComparison(
            metric=metric,
            control_mean=ctrl_mean,
            treatment_mean=treat_mean,
            delta=delta,
            relative_change_pct=relative_pct,
            n_pairs=len(control_vals),
            cohens_d=_cohens_d(control_vals, treatment_vals),
        ))

    return comparisons


def compute_convergence_stats(records: list[TrialRecord]) -> ConvergenceStats:
    """Compute statistics about the treatment revision loop.

    Args:
        records: All trial records (filters to treatment only).

    Returns:
        Aggregate convergence statistics.
    """
    treatment = [r for r in records if r.get("condition") == "treatment"]
    if not treatment:
        return ConvergenceStats(
            mean_revisions=0.0, convergence_rate=0.0,
            mean_initial_score=0.0, mean_final_score=0.0,
            mean_score_lift=0.0,
        )

    revisions = [float(r.get("revision_count", 0)) for r in treatment]  # type: ignore[arg-type]
    converged = [1.0 if r.get("converged") else 0.0 for r in treatment]
    initial_scores = [float(r.get("initial_score", 0)) for r in treatment]  # type: ignore[arg-type]
    final_scores = [float(r.get("final_score", 0)) for r in treatment]  # type: ignore[arg-type]
    lifts = [f - i for i, f in zip(initial_scores, final_scores)]

    return ConvergenceStats(
        mean_revisions=_mean(revisions),
        convergence_rate=_mean(converged),
        mean_initial_score=_mean(initial_scores),
        mean_final_score=_mean(final_scores),
        mean_score_lift=_mean(lifts),
    )


def detect_gaming(records: list[TrialRecord]) -> list[GamingDetection]:
    """Detect per-task gaming: slop score up but external quality down.

    A gaming flag is raised when the slop-guard score improves by at least 10
    points but two or more of these external signals degrade:
        - type_token_ratio drops (less lexical diversity)
        - hapax_ratio drops (fewer unique words)
        - sentence_length_cv drops (more monotonous rhythm)
        - flesch_kincaid_grade increases by 2+ (less readable)

    Args:
        records: All trial records.

    Returns:
        One GamingDetection per task with paired control/treatment data.
    """
    groups = _group_by_task(records)
    detections: list[GamingDetection] = []

    for task_records in groups.values():
        ctrl = [r for r in task_records if r.get("condition") == "control"]
        treat = [r for r in task_records if r.get("condition") == "treatment"]
        if not ctrl or not treat:
            continue

        c, t = ctrl[0], treat[0]
        slop_delta = (
            float(t.get("final_score", 0))  # type: ignore[arg-type]
            - float(c.get("final_score", 0))  # type: ignore[arg-type]
        )
        ttr_delta = _extract_metric(t, "type_token_ratio") - _extract_metric(c, "type_token_ratio")
        hapax_delta = _extract_metric(t, "hapax_ratio") - _extract_metric(c, "hapax_ratio")
        cv_delta = _extract_metric(t, "sentence_length_cv") - _extract_metric(c, "sentence_length_cv")
        fk_delta = _extract_metric(t, "flesch_kincaid_grade") - _extract_metric(c, "flesch_kincaid_grade")

        degradation_count = sum([
            ttr_delta < -0.01,
            hapax_delta < -0.01,
            cv_delta < -0.05,
            fk_delta > 2.0,
        ])
        gaming_flag = slop_delta >= 10 and degradation_count >= 2

        detections.append(GamingDetection(
            slop_score_delta=slop_delta,
            type_token_ratio_delta=ttr_delta,
            hapax_ratio_delta=hapax_delta,
            sentence_length_cv_delta=cv_delta,
            flesch_kincaid_delta=fk_delta,
            gaming_flag=gaming_flag,
        ))

    return detections


def build_report(records: list[TrialRecord]) -> dict[str, object]:
    """Build a full evaluation report from trial records.

    Args:
        records: All trial records from one or more agents.

    Returns:
        Nested dictionary suitable for JSON serialization.
    """
    comparisons = compute_paired_comparisons(records)
    convergence = compute_convergence_stats(records)
    gaming = detect_gaming(records)

    gaming_flagged = sum(1 for g in gaming if g.gaming_flag)

    return {
        "summary": {
            "total_trials": len(records),
            "control_trials": sum(1 for r in records if r.get("condition") == "control"),
            "treatment_trials": sum(1 for r in records if r.get("condition") == "treatment"),
            "gaming_flags": gaming_flagged,
        },
        "paired_comparisons": [c.to_dict() for c in comparisons],
        "convergence": convergence.to_dict(),
        "gaming_detection": [g.to_dict() for g in gaming],
    }


def print_report(report: dict[str, object]) -> None:
    """Print a human-readable summary of the evaluation report."""
    summary = report.get("summary", {})
    print(f"=== Evaluation Report ===")
    print(f"Trials: {summary.get('total_trials', 0)} "
          f"(control={summary.get('control_trials', 0)}, "
          f"treatment={summary.get('treatment_trials', 0)})")
    print(f"Gaming flags: {summary.get('gaming_flags', 0)}")
    print()

    print("--- Paired Comparisons (treatment - control) ---")
    comparisons = report.get("paired_comparisons", [])
    for comp in comparisons:  # type: ignore[union-attr]
        if not isinstance(comp, dict):
            continue
        direction = "+" if comp.get("delta", 0) >= 0 else ""  # type: ignore[operator]
        print(
            f"  {comp['metric']:>25s}: "
            f"ctrl={comp['control_mean']:>8.3f}  "
            f"treat={comp['treatment_mean']:>8.3f}  "
            f"delta={direction}{comp['delta']:.3f}  "
            f"({direction}{comp['relative_change_pct']:.1f}%)  "
            f"d={comp['cohens_d']:.2f}"
        )
    print()

    convergence = report.get("convergence", {})
    print("--- Convergence (treatment only) ---")
    print(f"  Mean revisions:     {convergence.get('mean_revisions', 0):.1f}")  # type: ignore[union-attr]
    print(f"  Convergence rate:   {convergence.get('convergence_rate_pct', 0):.0f}%")  # type: ignore[union-attr]
    print(f"  Score lift:         {convergence.get('mean_initial_score', 0):.0f} -> "  # type: ignore[union-attr]
          f"{convergence.get('mean_final_score', 0):.0f} "  # type: ignore[union-attr]
          f"(+{convergence.get('mean_score_lift', 0):.0f})")  # type: ignore[union-attr]
    print()

    gaming = report.get("gaming_detection", [])
    flagged = [g for g in gaming if isinstance(g, dict) and g.get("gaming_flag")]  # type: ignore[union-attr]
    if flagged:
        print(f"--- Gaming Detection ({len(flagged)} flagged) ---")
        for g in flagged:
            print(f"  slop={g['slop_score_delta']:+.0f}  "
                  f"ttr={g['type_token_ratio_delta']:+.4f}  "
                  f"hapax={g['hapax_ratio_delta']:+.4f}  "
                  f"cv={g['sentence_length_cv_delta']:+.4f}  "
                  f"fk={g['flesch_kincaid_delta']:+.2f}")
    else:
        print("--- Gaming Detection: no flags ---")
