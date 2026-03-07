# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""External quality metrics independent of slop-guard scoring.

These metrics provide an orthogonal signal so we can verify that slop-guard
feedback genuinely improves writing quality rather than teaching agents to
game the slop-guard scoring function.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import TypeAlias

_WORD_RE = re.compile(r"[a-zA-Z]+(?:['-][a-zA-Z]+)*")
_SENTENCE_END_RE = re.compile(r"[.!?][\"'\u201D\u2019)\]]*(?:\s|$)")
_SYLLABLE_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)

MetricValues: TypeAlias = dict[str, float]


@dataclass(frozen=True)
class QualityMetrics:
    """Container for all external quality measurements on a single text."""

    word_count: int
    sentence_count: int
    type_token_ratio: float
    hapax_ratio: float
    avg_sentence_length: float
    sentence_length_cv: float
    flesch_kincaid_grade: float
    gunning_fog_index: float
    avg_word_length: float
    unique_word_pct: float
    paragraph_count: int
    avg_paragraph_length: float
    paragraph_length_cv: float

    def to_dict(self) -> MetricValues:
        """Serialize all metrics to a flat dictionary."""
        return {
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "type_token_ratio": round(self.type_token_ratio, 4),
            "hapax_ratio": round(self.hapax_ratio, 4),
            "avg_sentence_length": round(self.avg_sentence_length, 2),
            "sentence_length_cv": round(self.sentence_length_cv, 4),
            "flesch_kincaid_grade": round(self.flesch_kincaid_grade, 2),
            "gunning_fog_index": round(self.gunning_fog_index, 2),
            "avg_word_length": round(self.avg_word_length, 2),
            "unique_word_pct": round(self.unique_word_pct, 4),
            "paragraph_count": self.paragraph_count,
            "avg_paragraph_length": round(self.avg_paragraph_length, 2),
            "paragraph_length_cv": round(self.paragraph_length_cv, 4),
        }


def _count_syllables(word: str) -> int:
    """Estimate syllable count for a word using vowel-group heuristic."""
    matches = _SYLLABLE_RE.findall(word)
    count = len(matches)
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on terminal punctuation."""
    parts = _SENTENCE_END_RE.split(text)
    return [s.strip() for s in parts if s.strip()]


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs on blank lines."""
    raw = re.split(r"\n\s*\n", text)
    return [p.strip() for p in raw if p.strip()]


def _coefficient_of_variation(values: list[int | float]) -> float:
    """Compute CV (stddev / mean). Returns 0.0 for degenerate inputs."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance) / mean


def compute_quality_metrics(text: str) -> QualityMetrics:
    """Compute all external quality metrics for a text sample.

    Args:
        text: The prose to analyze.

    Returns:
        A frozen QualityMetrics instance with all measurements.
    """
    words = _WORD_RE.findall(text)
    word_count = len(words)
    lower_words = [w.lower() for w in words]
    word_freq = Counter(lower_words)
    unique_count = len(word_freq)

    type_token_ratio = unique_count / word_count if word_count else 0.0
    hapax_count = sum(1 for count in word_freq.values() if count == 1)
    hapax_ratio = hapax_count / word_count if word_count else 0.0
    unique_word_pct = unique_count / word_count if word_count else 0.0
    avg_word_length = (
        sum(len(w) for w in words) / word_count if word_count else 0.0
    )

    sentences = _split_sentences(text)
    sentence_count = max(len(sentences), 1)
    sentence_word_counts = [len(_WORD_RE.findall(s)) for s in sentences]
    avg_sentence_length = word_count / sentence_count
    sentence_length_cv = _coefficient_of_variation(sentence_word_counts)

    total_syllables = sum(_count_syllables(w) for w in words)
    avg_syllables_per_word = total_syllables / word_count if word_count else 0.0

    # Flesch-Kincaid Grade Level
    flesch_kincaid_grade = (
        0.39 * avg_sentence_length + 11.8 * avg_syllables_per_word - 15.59
    )

    # Gunning Fog Index
    complex_word_count = sum(
        1 for w in words if _count_syllables(w) >= 3
    )
    complex_word_pct = complex_word_count / word_count if word_count else 0.0
    gunning_fog_index = 0.4 * (avg_sentence_length + 100 * complex_word_pct)

    paragraphs = _split_paragraphs(text)
    paragraph_count = max(len(paragraphs), 1)
    paragraph_word_counts = [len(_WORD_RE.findall(p)) for p in paragraphs]
    avg_paragraph_length = word_count / paragraph_count
    paragraph_length_cv = _coefficient_of_variation(paragraph_word_counts)

    return QualityMetrics(
        word_count=word_count,
        sentence_count=sentence_count,
        type_token_ratio=type_token_ratio,
        hapax_ratio=hapax_ratio,
        avg_sentence_length=avg_sentence_length,
        sentence_length_cv=sentence_length_cv,
        flesch_kincaid_grade=flesch_kincaid_grade,
        gunning_fog_index=gunning_fog_index,
        avg_word_length=avg_word_length,
        unique_word_pct=unique_word_pct,
        paragraph_count=paragraph_count,
        avg_paragraph_length=avg_paragraph_length,
        paragraph_length_cv=paragraph_length_cv,
    )
