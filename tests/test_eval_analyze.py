"""Tests for the evaluation analysis module."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from eval.analyze import (
    ConvergenceStats,
    GamingDetection,
    PairedComparison,
    build_report,
    compute_convergence_stats,
    compute_paired_comparisons,
    detect_gaming,
)


def _make_record(
    task_id: str,
    condition: str,
    final_score: int,
    initial_score: int = 50,
    revision_count: int = 0,
    converged: bool = False,
    ttr: float = 0.6,
    hapax: float = 0.4,
    cv: float = 0.35,
    fk: float = 8.0,
) -> dict:
    return {
        "task_id": task_id,
        "agent": "test_agent",
        "condition": condition,
        "revision_count": revision_count,
        "converged": converged,
        "initial_score": initial_score,
        "final_score": final_score,
        "score_delta": final_score - initial_score,
        "initial_band": "moderate",
        "final_band": "clean" if final_score >= 80 else "light",
        "word_count": 500,
        "total_elapsed_seconds": 10.0,
        "final_quality_metrics": {
            "type_token_ratio": ttr,
            "hapax_ratio": hapax,
            "sentence_length_cv": cv,
            "flesch_kincaid_grade": fk,
            "gunning_fog_index": 10.0,
            "unique_word_pct": ttr,
            "avg_sentence_length": 15.0,
            "paragraph_length_cv": 0.3,
        },
        "initial_quality_metrics": {
            "type_token_ratio": ttr,
            "hapax_ratio": hapax,
            "sentence_length_cv": cv,
            "flesch_kincaid_grade": fk,
            "gunning_fog_index": 10.0,
            "unique_word_pct": ttr,
            "avg_sentence_length": 15.0,
            "paragraph_length_cv": 0.3,
        },
        "final_slop_counts": {},
        "final_violation_count": 0,
    }


class TestPairedComparisons:
    """Tests for compute_paired_comparisons."""

    def test_basic_comparison(self) -> None:
        records = [
            _make_record("t1", "control", final_score=50),
            _make_record("t1", "treatment", final_score=80),
        ]
        comps = compute_paired_comparisons(records, metrics=("score",))
        assert len(comps) == 1
        assert comps[0].metric == "score"
        assert comps[0].control_mean == 50.0
        assert comps[0].treatment_mean == 80.0
        assert comps[0].delta == 30.0
        assert comps[0].n_pairs == 1

    def test_multiple_tasks(self) -> None:
        records = [
            _make_record("t1", "control", final_score=40),
            _make_record("t1", "treatment", final_score=70),
            _make_record("t2", "control", final_score=60),
            _make_record("t2", "treatment", final_score=90),
        ]
        comps = compute_paired_comparisons(records, metrics=("score",))
        assert comps[0].n_pairs == 2
        assert comps[0].control_mean == 50.0
        assert comps[0].treatment_mean == 80.0

    def test_empty_records(self) -> None:
        comps = compute_paired_comparisons([], metrics=("score",))
        assert comps == []

    def test_serialization(self) -> None:
        comp = PairedComparison(
            metric="score", control_mean=50.0, treatment_mean=80.0,
            delta=30.0, relative_change_pct=60.0, n_pairs=5, cohens_d=1.2,
        )
        d = comp.to_dict()
        assert d["metric"] == "score"
        assert d["delta"] == 30.0


class TestConvergenceStats:
    """Tests for compute_convergence_stats."""

    def test_basic_convergence(self) -> None:
        records = [
            _make_record("t1", "treatment", final_score=85,
                         initial_score=50, revision_count=2, converged=True),
            _make_record("t2", "treatment", final_score=75,
                         initial_score=45, revision_count=3, converged=False),
        ]
        stats = compute_convergence_stats(records)
        assert stats.mean_revisions == 2.5
        assert stats.convergence_rate == 0.5
        assert stats.mean_score_lift == 32.5

    def test_filters_control(self) -> None:
        records = [
            _make_record("t1", "control", final_score=50),
            _make_record("t1", "treatment", final_score=85,
                         revision_count=1, converged=True),
        ]
        stats = compute_convergence_stats(records)
        assert stats.mean_revisions == 1.0

    def test_empty(self) -> None:
        stats = compute_convergence_stats([])
        assert stats.mean_revisions == 0.0
        assert stats.convergence_rate == 0.0

    def test_serialization(self) -> None:
        stats = ConvergenceStats(
            mean_revisions=1.5, convergence_rate=0.8,
            mean_initial_score=45.0, mean_final_score=82.0,
            mean_score_lift=37.0,
        )
        d = stats.to_dict()
        assert d["convergence_rate_pct"] == 80.0


class TestGamingDetection:
    """Tests for detect_gaming."""

    def test_no_gaming(self) -> None:
        records = [
            _make_record("t1", "control", final_score=50, ttr=0.6, hapax=0.4, cv=0.35, fk=8.0),
            _make_record("t1", "treatment", final_score=80, ttr=0.65, hapax=0.45, cv=0.40, fk=7.0),
        ]
        detections = detect_gaming(records)
        assert len(detections) == 1
        assert not detections[0].gaming_flag

    def test_gaming_detected(self) -> None:
        records = [
            _make_record("t1", "control", final_score=50, ttr=0.65, hapax=0.45, cv=0.40, fk=8.0),
            _make_record("t1", "treatment", final_score=85, ttr=0.50, hapax=0.30, cv=0.25, fk=12.0),
        ]
        detections = detect_gaming(records)
        assert len(detections) == 1
        assert detections[0].gaming_flag

    def test_score_improvement_too_small(self) -> None:
        records = [
            _make_record("t1", "control", final_score=70, ttr=0.65, hapax=0.45, cv=0.40, fk=8.0),
            _make_record("t1", "treatment", final_score=75, ttr=0.50, hapax=0.30, cv=0.25, fk=12.0),
        ]
        detections = detect_gaming(records)
        assert not detections[0].gaming_flag

    def test_serialization(self) -> None:
        g = GamingDetection(
            slop_score_delta=20.0, type_token_ratio_delta=-0.1,
            hapax_ratio_delta=-0.15, sentence_length_cv_delta=-0.1,
            flesch_kincaid_delta=3.0, gaming_flag=True,
        )
        d = g.to_dict()
        assert d["gaming_flag"] is True


class TestBuildReport:
    """Tests for build_report."""

    def test_full_report_structure(self) -> None:
        records = [
            _make_record("t1", "control", final_score=50),
            _make_record("t1", "treatment", final_score=85,
                         revision_count=2, converged=True),
        ]
        report = build_report(records)
        assert "summary" in report
        assert "paired_comparisons" in report
        assert "convergence" in report
        assert "gaming_detection" in report
        assert report["summary"]["total_trials"] == 2  # type: ignore[index]

    def test_empty_records(self) -> None:
        report = build_report([])
        assert report["summary"]["total_trials"] == 0  # type: ignore[index]
