"""Tests for the evaluation quality metrics module."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow imports from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from eval.metrics import QualityMetrics, compute_quality_metrics


class TestComputeQualityMetrics:
    """Tests for compute_quality_metrics."""

    SAMPLE_TEXT = (
        "The quick brown fox jumps over the lazy dog. "
        "Pack my box with five dozen liquor jugs. "
        "How vexingly quick daft zebras jump."
    )

    def test_word_count(self) -> None:
        result = compute_quality_metrics(self.SAMPLE_TEXT)
        assert result.word_count > 0

    def test_sentence_count(self) -> None:
        result = compute_quality_metrics(self.SAMPLE_TEXT)
        assert result.sentence_count == 3

    def test_type_token_ratio_range(self) -> None:
        result = compute_quality_metrics(self.SAMPLE_TEXT)
        assert 0.0 < result.type_token_ratio <= 1.0

    def test_hapax_ratio_range(self) -> None:
        result = compute_quality_metrics(self.SAMPLE_TEXT)
        assert 0.0 <= result.hapax_ratio <= 1.0

    def test_sentence_length_cv_positive(self) -> None:
        result = compute_quality_metrics(self.SAMPLE_TEXT)
        assert result.sentence_length_cv >= 0.0

    def test_flesch_kincaid_reasonable(self) -> None:
        result = compute_quality_metrics(self.SAMPLE_TEXT)
        assert -5.0 < result.flesch_kincaid_grade < 30.0

    def test_gunning_fog_reasonable(self) -> None:
        result = compute_quality_metrics(self.SAMPLE_TEXT)
        assert 0.0 < result.gunning_fog_index < 30.0

    def test_to_dict_keys(self) -> None:
        result = compute_quality_metrics(self.SAMPLE_TEXT)
        d = result.to_dict()
        expected_keys = {
            "word_count", "sentence_count", "type_token_ratio",
            "hapax_ratio", "avg_sentence_length", "sentence_length_cv",
            "flesch_kincaid_grade", "gunning_fog_index", "avg_word_length",
            "unique_word_pct", "paragraph_count", "avg_paragraph_length",
            "paragraph_length_cv",
        }
        assert set(d.keys()) == expected_keys

    def test_empty_text(self) -> None:
        result = compute_quality_metrics("")
        assert result.word_count == 0
        assert result.type_token_ratio == 0.0

    def test_single_word(self) -> None:
        result = compute_quality_metrics("Hello")
        assert result.word_count == 1
        assert result.type_token_ratio == 1.0

    def test_multi_paragraph(self) -> None:
        text = "First paragraph here.\n\nSecond paragraph here.\n\nThird one."
        result = compute_quality_metrics(text)
        assert result.paragraph_count == 3

    def test_repetitive_text_low_ttr(self) -> None:
        text = "the the the the the the the the the the. " * 5
        result = compute_quality_metrics(text)
        assert result.type_token_ratio < 0.3

    def test_diverse_text_high_ttr(self) -> None:
        text = (
            "Astronomers discovered a peculiar exoplanet orbiting "
            "a binary star system. Geologists meanwhile catalogued "
            "previously unknown mineral formations beneath the "
            "Antarctic ice sheet."
        )
        result = compute_quality_metrics(text)
        assert result.type_token_ratio > 0.7

    def test_frozen_dataclass(self) -> None:
        result = compute_quality_metrics(self.SAMPLE_TEXT)
        try:
            result.word_count = 999  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass


class TestComputeQualityMetricsEdgeCases:
    """Edge case tests for quality metrics."""

    def test_only_punctuation(self) -> None:
        result = compute_quality_metrics("!!! ??? ...")
        assert result.word_count == 0

    def test_code_block_text(self) -> None:
        text = "Here is an example.\n\n```python\nprint('hello')\n```\n\nDone."
        result = compute_quality_metrics(text)
        assert result.word_count > 0

    def test_bullet_list(self) -> None:
        text = "Features:\n- Fast execution\n- Low memory\n- Simple API"
        result = compute_quality_metrics(text)
        assert result.word_count > 0
