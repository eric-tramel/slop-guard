"""Integration tests for rule-pipeline based analysis output."""

from __future__ import annotations

from slop_guard.analysis import HYPERPARAMETERS
from slop_guard.server import _analyze


def test_analyze_runs_instantiated_rule_pipeline() -> None:
    """Analyze should emit expected schema and detect rule hits."""
    text = (
        "This is a crucial and groundbreaking paradigm that feels remarkably "
        "innovative and comprehensive overall."
    )

    result = _analyze(text, HYPERPARAMETERS)

    assert set(result) == {
        "score",
        "band",
        "word_count",
        "violations",
        "counts",
        "total_penalty",
        "weighted_sum",
        "density",
        "advice",
    }
    assert result["counts"]["slop_words"] >= 1
    assert any(v["rule"] == "slop_word" for v in result["violations"])


def test_analyze_short_text_uses_clean_short_circuit() -> None:
    """Short text should preserve score and payload defaults."""
    result = _analyze("too short", HYPERPARAMETERS)
    assert result["score"] == HYPERPARAMETERS.score_max
    assert result["violations"] == []
    assert result["advice"] == []
