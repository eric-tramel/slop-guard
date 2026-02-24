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
    if negative_rate <= positive_rate:
        return 0

    separation = negative_rate - positive_rate
    confidence = negative_total / (negative_total + positive_total + 6.0)
    scale = clamp_float(0.75 + (1.75 * separation) + (0.5 * confidence), 0.5, 2.5)
    magnitude = max(1, int(round(abs(baseline) * scale)))
    return -magnitude if base_penalty < 0 else magnitude


def _threshold_candidates(
    *,
    default_value: float,
    positive_values: NumericSeq,
    negative_values: NumericSeq,
    lower: float,
    upper: float,
) -> list[float]:
    """Build threshold candidates from default and empirical quantiles."""
    candidates = {clamp_float(default_value, lower, upper), lower, upper}
    combined = [float(value) for value in (*positive_values, *negative_values)]
    if not combined:
        return sorted(candidates)
    if len(combined) == 1:
        candidates.add(clamp_float(combined[0], lower, upper))
        return sorted(candidates)

    for index in range(21):
        quantile = index / 20.0
        candidates.add(clamp_float(percentile(combined, quantile), lower, upper))
    return sorted(candidates)


def _contrastive_rate_stats(
    *,
    threshold: float,
    positive_values: NumericSeq,
    negative_values: NumericSeq,
    mode: str,
) -> tuple[float, float]:
    """Return positive and negative match rates for one threshold."""
    if mode not in ("high", "low"):
        raise ValueError("mode must be 'high' or 'low'")

    if mode == "high":
        positive_hits = sum(1 for value in positive_values if float(value) > threshold)
        negative_hits = sum(1 for value in negative_values if float(value) > threshold)
    else:
        positive_hits = sum(1 for value in positive_values if float(value) < threshold)
        negative_hits = sum(1 for value in negative_values if float(value) < threshold)

    positive_rate = positive_hits / len(positive_values) if positive_values else 0.0
    negative_rate = negative_hits / len(negative_values) if negative_values else 0.0
    return positive_rate, negative_rate


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

    default_clamped = clamp_float(default_value, lower, upper)
    candidates = _threshold_candidates(
        default_value=default_clamped,
        positive_values=positive_values,
        negative_values=negative_values,
        lower=lower,
        upper=upper,
    )
    candidates.extend(
        (
            clamp_float(percentile(positive_values, positive_quantile), lower, upper),
            clamp_float(percentile(positive_values, 0.99), lower, upper),
        )
    )
    if negative_values:
        candidates.extend(
            (
                clamp_float(percentile(negative_values, negative_quantile), lower, upper),
                clamp_float(percentile(negative_values, 0.01), lower, upper),
            )
        )
    candidates = sorted(set(candidates))

    best_candidate = default_clamped
    best_gap = float("-inf")
    best_key = (float("-inf"), float("-inf"), float("-inf"), float("-inf"))
    for candidate in candidates:
        positive_rate, negative_rate = _contrastive_rate_stats(
            threshold=candidate,
            positive_values=positive_values,
            negative_values=negative_values,
            mode="high",
        )
        gap = negative_rate - positive_rate
        objective = -positive_rate
        if negative_values:
            objective = gap - (0.40 * positive_rate)
            if positive_rate <= 0.20:
                objective += 0.10
            if negative_rate <= positive_rate:
                objective -= 0.25
        key = (objective, gap, -positive_rate, negative_rate)
        if key > best_key:
            best_key = key
            best_gap = gap
            best_candidate = candidate

    if negative_values and best_gap <= 0.0:
        return default_clamped

    blended = blend_toward_default_float(
        default_clamped,
        best_candidate,
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

    default_clamped = clamp_float(default_value, lower, upper)
    candidates = _threshold_candidates(
        default_value=default_clamped,
        positive_values=positive_values,
        negative_values=negative_values,
        lower=lower,
        upper=upper,
    )
    candidates.extend(
        (
            clamp_float(percentile(positive_values, positive_quantile), lower, upper),
            clamp_float(percentile(positive_values, 0.01), lower, upper),
        )
    )
    if negative_values:
        candidates.extend(
            (
                clamp_float(percentile(negative_values, negative_quantile), lower, upper),
                clamp_float(percentile(negative_values, 0.99), lower, upper),
            )
        )
    candidates = sorted(set(candidates))

    best_candidate = default_clamped
    best_gap = float("-inf")
    best_key = (float("-inf"), float("-inf"), float("-inf"), float("-inf"))
    for candidate in candidates:
        positive_rate, negative_rate = _contrastive_rate_stats(
            threshold=candidate,
            positive_values=positive_values,
            negative_values=negative_values,
            mode="low",
        )
        gap = negative_rate - positive_rate
        objective = -positive_rate
        if negative_values:
            objective = gap - (0.40 * positive_rate)
            if positive_rate <= 0.20:
                objective += 0.10
            if negative_rate <= positive_rate:
                objective -= 0.25
        key = (objective, gap, -positive_rate, negative_rate)
        if key > best_key:
            best_key = key
            best_gap = gap
            best_candidate = candidate

    if negative_values and best_gap <= 0.0:
        return default_clamped

    blended = blend_toward_default_float(
        default_clamped,
        best_candidate,
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

    default_clamped = clamp_int(default_value, lower, upper)
    cap_upper = clamp_int(int(round(default_clamped * max_multiplier)), lower, upper)
    candidates: set[int] = {default_clamped, lower, upper, cap_upper}
    combined = [float(value) for value in (*positive_values, *negative_values)]
    if len(combined) == 1:
        candidates.add(clamp_int(int(round(combined[0])), lower, upper))
    elif combined:
        for index in range(21):
            quantile = index / 20.0
            candidates.add(clamp_int(int(round(percentile(combined, quantile))), lower, upper))
    candidates.add(clamp_int(percentile_ceil(positive_values, positive_quantile), lower, upper))
    if negative_values:
        candidates.add(
            clamp_int(percentile_ceil(negative_values, negative_quantile), lower, upper)
        )

    best_candidate = default_clamped
    best_gap = float("-inf")
    best_key = (float("-inf"), float("-inf"), float("-inf"), float("-inf"))
    for candidate in sorted(candidates):
        positive_clipped_mean = (
            sum(min(float(value), candidate) for value in positive_values)
            / len(positive_values)
        )
        negative_clipped_mean = (
            sum(min(float(value), candidate) for value in negative_values)
            / len(negative_values)
            if negative_values
            else 0.0
        )
        positive_nonzero_rate = (
            sum(1 for value in positive_values if min(float(value), candidate) > 0.0)
            / len(positive_values)
        )
        negative_nonzero_rate = (
            sum(1 for value in negative_values if min(float(value), candidate) > 0.0)
            / len(negative_values)
            if negative_values
            else 0.0
        )
        gap = negative_clipped_mean - positive_clipped_mean
        objective = -positive_clipped_mean
        if negative_values:
            objective = gap - (0.25 * positive_clipped_mean)
            if positive_nonzero_rate <= 0.20:
                objective += 0.10
            if negative_nonzero_rate <= positive_nonzero_rate:
                objective -= 0.25
        key = (
            objective,
            gap,
            -positive_clipped_mean,
            negative_clipped_mean,
        )
        if key > best_key:
            best_key = key
            best_gap = gap
            best_candidate = candidate

    if negative_values and best_gap <= 0.0:
        return default_clamped

    blended = blend_toward_default_float(
        float(default_clamped),
        float(best_candidate),
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
