"""Scoring, counting, and violation serialization helpers."""

import math
import re
from collections.abc import Iterable

from .config import Hyperparameters
from .document import context_around
from .models import AnalysisPayload, BandLabel, Counts, Violation, ViolationPayload

_COUNT_KEYS: tuple[str, ...] = (
    "slop_words",
    "slop_phrases",
    "structural",
    "tone",
    "weasel",
    "ai_disclosure",
    "placeholder",
    "rhythm",
    "em_dash",
    "contrast_pairs",
    "setup_resolution",
    "colon_density",
    "pithy_fragment",
    "bullet_density",
    "blockquote_density",
    "bold_bullet_list",
    "horizontal_rules",
    "phrase_reuse",
    "copula_chain",
    "extreme_sentence",
    "closing_aphorism",
    "paragraph_balance",
    "paragraph_cv",
)


def initial_counts(count_keys: Iterable[str] | None = None) -> Counts:
    """Create the canonical per-rule counter map used by the analyzer."""
    keys = _COUNT_KEYS if count_keys is None else tuple(dict.fromkeys(count_keys))
    return {key: 0 for key in keys}


def _literal_span_candidates(text: str, match: str) -> tuple[tuple[int, int], ...]:
    """Return case-insensitive exact-text match spans for ``match``."""
    if not match:
        return ()
    return tuple(
        (occurrence.start(), occurrence.end())
        for occurrence in re.finditer(re.escape(match), text, flags=re.IGNORECASE)
    )


def _context_core(context: str) -> str:
    """Return the searchable body of a context snippet without ellipses."""
    start = 3 if context.startswith("...") else 0
    end = len(context) - 3 if context.endswith("...") else len(context)
    return context[start:end]


def _context_span_candidates(
    normalized_text: str,
    context: str,
) -> tuple[tuple[int, int], ...]:
    """Return spans where the normalized context snippet occurs in ``text``."""
    core = _context_core(context)
    if not core:
        return ()

    spans: list[tuple[int, int]] = []
    start = 0
    while True:
        index = normalized_text.find(core, start)
        if index < 0:
            return tuple(spans)
        spans.append((index, index + len(core)))
        start = index + 1


def _select_unused_span(
    candidates: tuple[tuple[int, int], ...],
    used_spans: set[tuple[int, int]],
) -> tuple[int, int] | None:
    """Return the first candidate span not already used, else the first match."""
    for span in candidates:
        if span not in used_spans:
            return span
    return candidates[0] if candidates else None


def _resolve_violation_span(
    violation: Violation,
    text: str,
    normalized_text: str,
    context_window_chars: int,
    used_spans: set[tuple[int, int]],
) -> tuple[int, int]:
    """Resolve a best-effort character span for a violation payload."""
    explicit_span = violation.explicit_span()
    if explicit_span is not None:
        return explicit_span

    literal_candidates = _literal_span_candidates(text, violation.match)
    context_matched_literal_candidates = tuple(
        span
        for span in literal_candidates
        if context_around(text, span[0], span[1], context_window_chars)
        == violation.context
    )
    literal_span = _select_unused_span(context_matched_literal_candidates, used_spans)
    if literal_span is not None:
        return literal_span

    if violation.match.casefold() in violation.context.casefold():
        literal_span = _select_unused_span(literal_candidates, used_spans)
        if literal_span is not None:
            return literal_span

    context_span = _select_unused_span(
        _context_span_candidates(normalized_text, violation.context),
        used_spans,
    )
    if context_span is not None:
        return context_span

    return (0, len(text))


def serialize_violations(
    violations: Iterable[Violation],
    text: str,
    context_window_chars: int,
) -> list[ViolationPayload]:
    """Serialize violations and attach resolved character offsets."""
    normalized_text = text.replace("\n", " ")
    used_spans: set[tuple[int, int]] = set()
    payloads: list[ViolationPayload] = []

    for violation in violations:
        start, end = _resolve_violation_span(
            violation,
            text,
            normalized_text,
            context_window_chars,
            used_spans,
        )
        used_spans.add((start, end))
        payloads.append(violation.to_payload(start, end))

    return payloads


def short_text_result(
    word_count_value: int,
    counts: Counts,
    hyperparameters: Hyperparameters,
) -> AnalysisPayload:
    """Build the fixed response shape for short texts that are skipped."""
    return {
        "score": hyperparameters.score_max,
        "band": "clean",
        "word_count": word_count_value,
        "violations": [],
        "counts": counts,
        "total_penalty": 0,
        "weighted_sum": 0.0,
        "density": 0.0,
        "advice": [],
    }


def compute_weighted_sum(
    violations: list[Violation],
    counts: Counts,
    hyperparameters: Hyperparameters,
) -> float:
    """Compute weighted penalties with concentration amplification."""
    weighted_sum = 0.0
    for violation in violations:
        rule = violation.rule
        penalty = abs(violation.penalty)
        cat_count = counts.get(rule, 0) or counts.get(rule + "s", 0)
        count_key = (
            rule
            if rule in hyperparameters.claude_categories
            else (
                rule + "s"
                if (rule + "s") in hyperparameters.claude_categories
                else None
            )
        )
        if (
            count_key
            and count_key in hyperparameters.claude_categories
            and cat_count > 1
        ):
            weight = penalty * (
                1 + hyperparameters.concentration_alpha * (cat_count - 1)
            )
        else:
            weight = penalty
        weighted_sum += weight
    return weighted_sum


def band_for_score(score: int, hyperparameters: Hyperparameters) -> BandLabel:
    """Map a numeric score into the configured severity band."""
    if score >= hyperparameters.band_clean_min:
        return "clean"
    if score >= hyperparameters.band_light_min:
        return "light"
    if score >= hyperparameters.band_moderate_min:
        return "moderate"
    if score >= hyperparameters.band_heavy_min:
        return "heavy"
    return "saturated"


def deduplicate_advice(advice: list[str]) -> list[str]:
    """Return advice entries preserving order while removing duplicates."""
    seen: set[str] = set()
    unique: list[str] = []
    for item in advice:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def score_from_density(density: float, hyperparameters: Hyperparameters) -> int:
    """Compute bounded integer score from weighted density."""
    raw_score = hyperparameters.score_max * math.exp(
        -hyperparameters.decay_lambda * density
    )
    return max(
        hyperparameters.score_min,
        min(hyperparameters.score_max, round(raw_score)),
    )
