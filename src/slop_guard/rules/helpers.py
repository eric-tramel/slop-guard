"""Shared helper functions used by multiple rule modules."""


import math
import re
from typing import TypeAlias

from slop_guard.analysis import Hyperparameters

NGramHit: TypeAlias = dict[str, int | str]
TokenSeq: TypeAlias = tuple[str, ...] | list[str]
NumericSeq: TypeAlias = list[int] | list[float]

_PUNCT_STRIP_RE = re.compile(r"^[^\w]+|[^\w]+$")
_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "is",
        "it",
        "that",
        "this",
        "with",
        "as",
        "by",
        "from",
        "was",
        "were",
        "are",
        "be",
        "been",
        "has",
        "have",
        "had",
        "not",
        "no",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "can",
        "may",
        "might",
        "if",
        "then",
        "than",
        "so",
        "up",
        "out",
        "about",
        "into",
        "over",
        "after",
        "before",
        "between",
        "through",
        "just",
        "also",
        "very",
        "more",
        "most",
        "some",
        "any",
        "each",
        "every",
        "all",
        "both",
        "few",
        "other",
        "such",
        "only",
        "own",
        "same",
        "too",
        "how",
        "what",
        "which",
        "who",
        "when",
        "where",
        "why",
    }
)


def clamp_int(value: int, lower: int, upper: int) -> int:
    """Clamp an integer into ``[lower, upper]``."""
    if lower > upper:
        raise ValueError("lower must be <= upper")
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


def clamp_float(value: float, lower: float, upper: float) -> float:
    """Clamp a float into ``[lower, upper]``."""
    if lower > upper:
        raise ValueError("lower must be <= upper")
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


def percentile(values: NumericSeq, quantile: float) -> float:
    """Return linear-interpolated percentile for ``quantile`` in ``[0, 1]``."""
    if not values:
        raise ValueError("values must be non-empty")
    if quantile < 0.0 or quantile > 1.0:
        raise ValueError("quantile must be in [0, 1]")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = quantile * (len(ordered) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    lower_value = ordered[lower_index]
    upper_value = ordered[upper_index]
    fraction = position - lower_index
    return lower_value + ((upper_value - lower_value) * fraction)


def percentile_ceil(values: NumericSeq, quantile: float) -> int:
    """Return ``ceil(percentile(values, quantile))``."""
    return int(math.ceil(percentile(values, quantile)))


def percentile_floor(values: NumericSeq, quantile: float) -> int:
    """Return ``floor(percentile(values, quantile))``."""
    return int(math.floor(percentile(values, quantile)))


def fit_penalty(base_penalty: int, matched_documents: int, total_documents: int) -> int:
    """Scale penalty magnitude by document support in the fit corpus.

    Rare patterns become stricter and common patterns become more permissive.
    """
    if total_documents <= 0:
        raise ValueError("total_documents must be positive")
    support = matched_documents / total_documents
    scale = clamp_float(1.5 - support, 0.5, 1.75)
    magnitude = max(1, int(round(abs(base_penalty) * scale)))
    return -magnitude if base_penalty < 0 else magnitude


def blend_toward_default_float(
    default_value: float,
    candidate_value: float,
    support: int,
    *,
    pivot: float = 12.0,
) -> float:
    """Blend a fitted candidate back toward a default by support size."""
    if support < 0:
        raise ValueError("support must be non-negative")
    if pivot <= 0.0:
        raise ValueError("pivot must be positive")
    if support == 0:
        return default_value
    weight = support / (support + pivot)
    return (default_value * (1.0 - weight)) + (candidate_value * weight)


def fit_penalty_contrastive(
    *,
    base_penalty: int,
    positive_matches: int,
    positive_total: int,
    negative_matches: int,
    negative_total: int,
) -> int:
    """Fit penalty strength using positive-vs-negative prevalence contrast."""
    baseline = fit_penalty(base_penalty, positive_matches, positive_total)
    if negative_total <= 0:
        return baseline

    positive_rate = positive_matches / positive_total
    negative_rate = negative_matches / negative_total
    contrast = clamp_float(negative_rate - positive_rate, -1.0, 1.0)
    confidence = negative_total / (negative_total + 5.0)
    scale = clamp_float(1.0 + (contrast * confidence), 0.5, 2.0)
    magnitude = max(1, int(round(abs(baseline) * scale)))
    return -magnitude if base_penalty < 0 else magnitude


def fit_threshold_high_contrastive(
    *,
    default_value: float,
    positive_values: NumericSeq,
    negative_values: NumericSeq,
    lower: float,
    upper: float,
    positive_quantile: float = 0.90,
    negative_quantile: float = 0.10,
    blend_pivot: float = 12.0,
) -> float:
    """Fit ``x > threshold`` style thresholds from contrastive distributions."""
    if not positive_values:
        return clamp_float(default_value, lower, upper)

    positive_anchor = percentile(positive_values, positive_quantile)
    candidate = positive_anchor
    if negative_values:
        negative_anchor = percentile(negative_values, negative_quantile)
        if negative_anchor > positive_anchor:
            candidate = (positive_anchor + negative_anchor) * 0.5

    blended = blend_toward_default_float(
        default_value,
        candidate,
        len(positive_values) + len(negative_values),
        pivot=blend_pivot,
    )
    return clamp_float(blended, lower, upper)


def fit_threshold_low_contrastive(
    *,
    default_value: float,
    positive_values: NumericSeq,
    negative_values: NumericSeq,
    lower: float,
    upper: float,
    positive_quantile: float = 0.10,
    negative_quantile: float = 0.90,
    blend_pivot: float = 12.0,
) -> float:
    """Fit ``x < threshold`` style thresholds from contrastive distributions."""
    if not positive_values:
        return clamp_float(default_value, lower, upper)

    positive_anchor = percentile(positive_values, positive_quantile)
    candidate = positive_anchor
    if negative_values:
        negative_anchor = percentile(negative_values, negative_quantile)
        if positive_anchor > negative_anchor:
            candidate = (positive_anchor + negative_anchor) * 0.5

    blended = blend_toward_default_float(
        default_value,
        candidate,
        len(positive_values) + len(negative_values),
        pivot=blend_pivot,
    )
    return clamp_float(blended, lower, upper)


def fit_count_cap_contrastive(
    *,
    default_value: int,
    positive_values: NumericSeq,
    negative_values: NumericSeq,
    lower: int,
    upper: int,
    positive_quantile: float = 0.90,
    negative_quantile: float = 0.75,
    blend_pivot: float = 12.0,
    max_multiplier: float = 2.0,
) -> int:
    """Fit a count-like cap conservatively from contrastive distributions."""
    if not positive_values:
        return clamp_int(default_value, lower, upper)

    positive_anchor = percentile_ceil(positive_values, positive_quantile)
    candidate = positive_anchor
    if negative_values:
        negative_anchor = percentile_ceil(negative_values, negative_quantile)
        candidate = max(
            positive_anchor,
            min(negative_anchor, int(round(default_value * max_multiplier))),
        )

    blended = blend_toward_default_float(
        float(default_value),
        float(candidate),
        len(positive_values) + len(negative_values),
        pivot=blend_pivot,
    )
    return clamp_int(int(round(blended)), lower, upper)


def normalize_ngram_tokens(text: str) -> list[str]:
    """Normalize text into lowercase tokens with edge punctuation stripped."""
    raw_tokens = text.split()
    return [
        token for token in (_PUNCT_STRIP_RE.sub("", raw).lower() for raw in raw_tokens) if token
    ]


def has_repeated_ngram_prefix(
    *,
    token_ids: tuple[int, ...],
    base: int,
    n: int,
    min_count: int,
) -> bool:
    """Return true when any n-gram id sequence appears at least ``min_count`` times."""
    if n < 1:
        raise ValueError("n must be >= 1")
    if min_count < 2:
        return len(token_ids) >= n
    if len(token_ids) < n:
        return False

    end = len(token_ids) - n + 1
    counts: dict[int, int] = {}
    counts_get = counts.get
    if n == 1:
        for start in range(end):
            key = token_ids[start]
            next_count = counts_get(key, 0) + 1
            if next_count >= min_count:
                return True
            counts[key] = next_count
        return False
    if n == 2:
        for start in range(end):
            key = (token_ids[start] * base) + token_ids[start + 1]
            next_count = counts_get(key, 0) + 1
            if next_count >= min_count:
                return True
            counts[key] = next_count
        return False
    if n == 3:
        base_squared = base * base
        for start in range(end):
            key = (
                (token_ids[start] * base_squared)
                + (token_ids[start + 1] * base)
                + token_ids[start + 2]
            )
            next_count = counts_get(key, 0) + 1
            if next_count >= min_count:
                return True
            counts[key] = next_count
        return False
    for start in range(end):
        key = 0
        for offset in range(n):
            key = (key * base) + token_ids[start + offset]
        next_count = counts_get(key, 0) + 1
        if next_count >= min_count:
            return True
        counts[key] = next_count
    return False


def find_repeated_ngrams_from_tokens(tokens: TokenSeq, hp: Hyperparameters) -> list[NGramHit]:
    """Find repeated multi-word phrases and keep only maximal spans."""
    min_n = hp.repeated_ngram_min_n
    max_n = hp.repeated_ngram_max_n
    if len(tokens) < min_n:
        return []

    ngram_counts: dict[tuple[str, ...], int] = {}
    for n in range(min_n, max_n + 1):
        end = len(tokens) - n + 1
        for index in range(end):
            gram = tuple(tokens[index : index + n])
            ngram_counts[gram] = ngram_counts.get(gram, 0) + 1

    repeated = {
        gram: count
        for gram, count in ngram_counts.items()
        if count >= hp.repeated_ngram_min_count
        and not all(word in _STOPWORDS for word in gram)
    }
    if not repeated:
        return []

    to_remove: set[tuple[str, ...]] = set()
    sorted_grams = sorted(repeated.keys(), key=len, reverse=True)
    for index, longer in enumerate(sorted_grams):
        longer_str = " ".join(longer)
        for shorter in sorted_grams[index + 1 :]:
            if shorter in to_remove:
                continue
            shorter_str = " ".join(shorter)
            if shorter_str in longer_str and repeated[longer] >= repeated[shorter]:
                to_remove.add(shorter)

    results: list[NGramHit] = []
    for gram in sorted(repeated.keys(), key=lambda item: (-len(item), -repeated[item])):
        if gram in to_remove:
            continue
        results.append(
            {
                "phrase": " ".join(gram),
                "count": repeated[gram],
                "n": len(gram),
            }
        )
    return results


def find_repeated_ngrams(text: str, hp: Hyperparameters) -> list[NGramHit]:
    """Find repeated multi-word phrases and keep only maximal spans."""
    return find_repeated_ngrams_from_tokens(normalize_ngram_tokens(text), hp)
