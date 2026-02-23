"""Core analysis models and scoring helpers for slop-guard."""


import math
import re
from dataclasses import dataclass, field
from typing import TypeAlias

Counts: TypeAlias = dict[str, int]
ViolationPayload: TypeAlias = dict[str, object]


@dataclass(frozen=True)
class Hyperparameters:
    """Tunable thresholds, caps, and penalties used by the analyzer."""

    concentration_alpha: float = 2.5
    decay_lambda: float = 0.04
    claude_categories: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"contrast_pairs", "pithy_fragment", "setup_resolution"}
        )
    )

    context_window_chars: int = 60
    short_text_word_count: int = 10

    repeated_ngram_min_n: int = 4
    repeated_ngram_max_n: int = 8
    repeated_ngram_min_count: int = 3

    slop_word_penalty: int = -2
    slop_phrase_penalty: int = -3
    structural_bold_header_min: int = 3
    structural_bold_header_penalty: int = -5
    structural_bullet_run_min: int = 6
    structural_bullet_run_penalty: int = -3
    triadic_record_cap: int = 5
    triadic_penalty: int = -1
    triadic_advice_min: int = 3
    tone_penalty: int = -3
    sentence_opener_penalty: int = -2
    weasel_penalty: int = -2
    ai_disclosure_penalty: int = -10
    placeholder_penalty: int = -5
    rhythm_min_sentences: int = 5
    rhythm_cv_threshold: float = 0.3
    rhythm_penalty: int = -5
    em_dash_words_basis: float = 150.0
    em_dash_density_threshold: float = 1.0
    em_dash_penalty: int = -3
    contrast_record_cap: int = 5
    contrast_penalty: int = -1
    contrast_advice_min: int = 2
    setup_resolution_record_cap: int = 5
    setup_resolution_penalty: int = -3
    colon_words_basis: float = 150.0
    colon_density_threshold: float = 1.5
    colon_density_penalty: int = -3
    pithy_max_sentence_words: int = 6
    pithy_record_cap: int = 3
    pithy_penalty: int = -2
    bullet_density_threshold: float = 0.40
    bullet_density_penalty: int = -8
    blockquote_min_lines: int = 3
    blockquote_free_lines: int = 2
    blockquote_cap: int = 4
    blockquote_penalty_step: int = -3
    bold_bullet_run_min: int = 3
    bold_bullet_run_penalty: int = -5
    horizontal_rule_min: int = 4
    horizontal_rule_penalty: int = -3
    phrase_reuse_record_cap: int = 5
    phrase_reuse_penalty: int = -1

    density_words_basis: float = 1000.0
    score_min: int = 0
    score_max: int = 100
    band_clean_min: int = 80
    band_light_min: int = 60
    band_moderate_min: int = 40
    band_heavy_min: int = 20


HYPERPARAMETERS = Hyperparameters()


@dataclass(frozen=True)
class Violation:
    """Canonical violation record emitted by a rule."""

    rule: str
    match: str
    context: str
    penalty: int

    def to_payload(self) -> ViolationPayload:
        """Serialize a typed violation for tool output."""
        return {
            "type": "Violation",
            "rule": self.rule,
            "match": self.match,
            "context": self.context,
            "penalty": self.penalty,
        }


_SENTENCE_SPLIT_RE = re.compile(r"[.!?][\"'\u201D\u2019)\]]*(?:\s|$)")


@dataclass(frozen=True)
class AnalysisDocument:
    """Precomputed text views consumed by rules in forward passes."""

    text: str
    lines: tuple[str, ...]
    sentences: tuple[str, ...]
    word_count: int

    @classmethod
    def from_text(cls, text: str) -> "AnalysisDocument":
        """Build a document with line/sentence/word projections."""
        return cls(
            text=text,
            lines=tuple(text.split("\n")),
            sentences=tuple(
                s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()
            ),
            word_count=word_count(text),
        )


@dataclass
class RuleResult:
    """Output payload emitted by a single rule invocation."""

    violations: list[Violation] = field(default_factory=list)
    advice: list[str] = field(default_factory=list)
    count_deltas: Counts = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisState:
    """Immutable accumulator carrying merged rule output."""

    violations: tuple[Violation, ...]
    advice: tuple[str, ...]
    counts: Counts

    @classmethod
    def initial(cls) -> "AnalysisState":
        """Construct an empty state with canonical counts initialized to zero."""
        return cls(violations=(), advice=(), counts=initial_counts())

    def merge(self, result: RuleResult) -> "AnalysisState":
        """Merge one rule result into a new state instance."""
        merged_counts = dict(self.counts)
        for key, delta in result.count_deltas.items():
            if delta:
                merged_counts[key] = merged_counts.get(key, 0) + delta

        return AnalysisState(
            violations=self.violations + tuple(result.violations),
            advice=self.advice + tuple(result.advice),
            counts=merged_counts,
        )


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
    "colon_density",
    "pithy_fragment",
    "setup_resolution",
    "bullet_density",
    "blockquote_density",
    "bold_bullet_list",
    "horizontal_rules",
    "phrase_reuse",
)


def initial_counts() -> Counts:
    """Create the canonical per-rule counter map used by the analyzer."""
    return {key: 0 for key in _COUNT_KEYS}


def context_around(
    text: str,
    start: int,
    end: int,
    width: int,
) -> str:
    """Extract a text snippet centered on the matched span."""
    mid = (start + end) // 2
    half = width // 2
    ctx_start = max(0, mid - half)
    ctx_end = min(len(text), mid + half)
    snippet = text[ctx_start:ctx_end].replace("\n", " ")
    prefix = "..." if ctx_start > 0 else ""
    suffix = "..." if ctx_end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


def word_count(text: str) -> int:
    """Return the whitespace-delimited word count for a text blob."""
    return len(text.split())


def short_text_result(word_count_value: int, counts: Counts, hp: Hyperparameters) -> dict:
    """Build the fixed response shape for short texts that are skipped."""
    return {
        "score": hp.score_max,
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
    violations: list[Violation], counts: Counts, hp: Hyperparameters
) -> float:
    """Compute weighted penalties with concentration amplification."""
    weighted_sum = 0.0
    for violation in violations:
        rule = violation.rule
        penalty = abs(violation.penalty)
        cat_count = counts.get(rule, 0) or counts.get(rule + "s", 0)
        count_key = (
            rule
            if rule in hp.claude_categories
            else (rule + "s" if (rule + "s") in hp.claude_categories else None)
        )
        if count_key and count_key in hp.claude_categories and cat_count > 1:
            weight = penalty * (1 + hp.concentration_alpha * (cat_count - 1))
        else:
            weight = penalty
        weighted_sum += weight
    return weighted_sum


def band_for_score(score: int, hp: Hyperparameters) -> str:
    """Map a numeric score into the configured severity band."""
    if score >= hp.band_clean_min:
        return "clean"
    if score >= hp.band_light_min:
        return "light"
    if score >= hp.band_moderate_min:
        return "moderate"
    if score >= hp.band_heavy_min:
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


def score_from_density(density: float, hp: Hyperparameters) -> int:
    """Compute bounded integer score from weighted density."""
    raw_score = hp.score_max * math.exp(-hp.decay_lambda * density)
    return max(hp.score_min, min(hp.score_max, round(raw_score)))
