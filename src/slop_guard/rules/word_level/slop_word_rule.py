"""Detect overused AI-associated slop words.

Objective: Identify stock adjectives, verbs, nouns, and hedges that make prose
sound inflated, generic, or model-generated instead of concrete and specific.

Example Rule Violations:
    - "This is a crucial, groundbreaking paradigm for modern teams."
      Uses stacked hype words instead of concrete claims.
    - "We can seamlessly leverage a robust framework to unlock outcomes."
      Uses multiple stock verbs and adjectives common in template prose.

Example Non-Violations:
    - "This patch removes an O(n^2) loop in the tokenizer."
      Specific technical claim with no hype vocabulary.
    - "P95 latency dropped from 180 ms to 95 ms after batching writes."
      Concrete measurement, not promotional phrasing.

Severity: Low to medium per hit; repeated hits are stronger evidence of generic
language and accumulate penalty quickly.
"""


from collections import Counter
import re
from dataclasses import dataclass
from typing import TypeAlias

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import fit_penalty_contrastive

_SLOP_ADJECTIVES = (
    "crucial",
    "groundbreaking",
    "pivotal",
    "paramount",
    "seamless",
    "holistic",
    "multifaceted",
    "meticulous",
    "profound",
    "comprehensive",
    "invaluable",
    "notable",
    "noteworthy",
    "game-changing",
    "revolutionary",
    "pioneering",
    "visionary",
    "formidable",
    "quintessential",
    "unparalleled",
    "stunning",
    "breathtaking",
    "captivating",
    "nestled",
    "robust",
    "innovative",
    "cutting-edge",
    "impactful",
    "foundational",
    "actionable",
    "collaborative",
    "societal",
    "impeccable",
    "stylistic",
)

_SLOP_VERBS = (
    "delve",
    "delves",
    "delved",
    "delving",
    "embark",
    "embrace",
    "elevate",
    "foster",
    "harness",
    "unleash",
    "unlock",
    "orchestrate",
    "streamline",
    "transcend",
    "navigate",
    "underscore",
    "showcase",
    "leverage",
    "ensuring",
    "highlighting",
    "emphasizing",
    "reflecting",
    "reshape",
)

_SLOP_NOUNS = (
    "landscape",
    "tapestry",
    "journey",
    "paradigm",
    "testament",
    "trajectory",
    "nexus",
    "symphony",
    "spectrum",
    "odyssey",
    "pinnacle",
    "realm",
    "intricacies",
    "ecosystem",
    "authenticity",
    "narrative",
    "perseverance",
)

_SLOP_HEDGE = (
    # Keep routine transitions like "however" and "furthermore" out of this
    # list. They are standard connective prose, not AI-slop markers.
    "significantly",
    "interestingly",
    "remarkably",
    "surprisingly",
    "fascinatingly",
    "subtly",
)

_ALL_SLOP_WORDS = _SLOP_ADJECTIVES + _SLOP_VERBS + _SLOP_NOUNS + _SLOP_HEDGE
_PLAIN_SLOP_WORDS: frozenset[str] = frozenset(
    word for word in _ALL_SLOP_WORDS if "-" not in word
)
_HYPHENATED_SLOP_WORDS: tuple[str, ...] = tuple(
    word for word in _ALL_SLOP_WORDS if "-" in word
)
_SLOP_ADJECTIVE_SET: frozenset[str] = frozenset(_SLOP_ADJECTIVES)
_SLOP_VERB_SET: frozenset[str] = frozenset(_SLOP_VERBS)
_SLOP_HEDGE_SET: frozenset[str] = frozenset(_SLOP_HEDGE)
_SLOP_SYSTEM_NOUNS: frozenset[str] = frozenset(
    {"ecosystem", "landscape", "nexus", "realm", "spectrum", "symphony", "tapestry"}
)
_SLOP_TIMELINE_NOUNS: frozenset[str] = frozenset(
    {"journey", "narrative", "odyssey", "trajectory"}
)
_SLOP_WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(word) for word in _ALL_SLOP_WORDS) + r")\b",
    re.IGNORECASE,
)
_TITLE_CASE_NAME_TOKEN_RE = re.compile(r"[A-Z][a-z]+(?:['-][A-Z][a-z]+)*|[A-Z]\.")
WordSpan: TypeAlias = tuple[int, int]


def _occurrence_suffix(count: int) -> str:
    """Return a stable occurrence suffix for grouped advice lines."""
    if count <= 1:
        return ""
    return f" ({count} occurrences)"


def _slop_word_advice(word: str, count: int) -> str:
    """Return category-specific rewrite advice for a matched slop word."""
    suffix = _occurrence_suffix(count)
    if word in _SLOP_HEDGE_SET:
        return (
            f"Cut '{word}'{suffix} — start the sentence directly or show the "
            "connection without announcing it."
        )
    if word in _SLOP_VERB_SET:
        return (
            f"Replace '{word}'{suffix} with the specific action, result, or evidence."
        )
    if word in _SLOP_SYSTEM_NOUNS:
        return (
            f"Replace '{word}'{suffix} with the concrete system, group, or thing you mean."
        )
    if word in _SLOP_TIMELINE_NOUNS:
        return (
            f"Replace '{word}'{suffix} with the actual period, step, or change you observed."
        )
    if word in _SLOP_ADJECTIVE_SET:
        return (
            f"Cut '{word}'{suffix} unless you can name the concrete property, metric, "
            "or consequence."
        )
    return f"Replace '{word}'{suffix} with the concrete object, event, or claim."


def _previous_word_span(text: str, start: int) -> WordSpan | None:
    """Return the previous word-like span before ``start`` when one exists."""
    index = start - 1
    while index >= 0 and text[index].isspace():
        index -= 1
    if index < 0 or not text[index].isalpha():
        return None

    end = index + 1
    while index >= 0 and (text[index].isalpha() or text[index] in "'.-"):
        index -= 1
    span = (index + 1, end)
    return span if span[0] < span[1] else None


def _next_word_span(text: str, end: int) -> WordSpan | None:
    """Return the next word-like span after ``end`` when one exists."""
    index = end
    while index < len(text) and text[index].isspace():
        index += 1
    if index >= len(text) or not text[index].isalpha():
        return None

    start = index
    while index < len(text) and (text[index].isalpha() or text[index] in "'.-"):
        index += 1
    span = (start, index)
    return span if span[0] < span[1] else None


def _is_probable_proper_noun_match(text: str, match: re.Match[str]) -> bool:
    """Return whether a hit looks like part of a title-cased name phrase."""
    matched_text = match.group(0)
    if not matched_text[:1].isupper():
        return False

    previous_span = _previous_word_span(text, match.start())
    if previous_span is not None:
        previous_token = text[previous_span[0] : previous_span[1]]
        if _TITLE_CASE_NAME_TOKEN_RE.fullmatch(previous_token) is not None:
            return True

    next_span = _next_word_span(text, match.end())
    if next_span is None:
        return False

    next_token = text[next_span[0] : next_span[1]]
    return _TITLE_CASE_NAME_TOKEN_RE.fullmatch(next_token) is not None


@dataclass
class SlopWordRuleConfig(RuleConfig):
    """Config for slop word matching behavior."""

    penalty: int
    context_window_chars: int


class SlopWordRule(Rule[SlopWordRuleConfig]):
    """Record one violation for each matched slop word."""

    name = "slop_word"
    count_key = "slop_words"
    level = RuleLevel.WORD

    def example_violations(self) -> list[str]:
        """Return samples that should trigger slop-word matches."""
        return [
            "This is a crucial and groundbreaking update.",
            "We can leverage a robust paradigm for growth.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid slop-word matches."""
        return [
            "This patch removes an O(n^2) loop in parsing.",
            "P95 latency dropped from 180 ms to 95 ms after batching writes.",
            "However, three reports still need one indexed join.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply the slop-word detector to the full text."""
        violations: list[Violation] = []
        word_counts: Counter[str] = Counter()
        advice_order: list[str] = []
        count = 0
        masked_text = document.text_with_markdown_code_masked

        has_plain_slop_token = bool(
            document.word_token_set_lower_with_markdown_code_masked
            & _PLAIN_SLOP_WORDS
        )
        has_hyphen_slop_fragment = any(
            word in document.lower_text_with_markdown_code_masked
            for word in _HYPHENATED_SLOP_WORDS
        )
        if not has_plain_slop_token and not has_hyphen_slop_fragment:
            return RuleResult()

        for match in _SLOP_WORD_RE.finditer(masked_text):
            if _is_probable_proper_noun_match(document.text, match):
                continue
            word = match.group(0).lower()
            violations.append(
                Violation(
                    rule=self.name,
                    match=word,
                    context=context_around(
                        document.text,
                        match.start(),
                        match.end(),
                        width=self.config.context_window_chars,
                    ),
                    penalty=self.config.penalty,
                    start=match.start(),
                    end=match.end(),
                )
            )
            if word_counts[word] == 0:
                advice_order.append(word)
            word_counts[word] += 1
            count += 1

        return RuleResult(
            violations=violations,
            advice=[_slop_word_advice(word, word_counts[word]) for word in advice_order],
            count_deltas={self.count_key: count} if count else {},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> SlopWordRuleConfig:
        """Fit penalty strength from observed slop-word prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_matches = sum(
            1
            for sample in positive_samples
            if _SLOP_WORD_RE.search(
                AnalysisDocument.from_text(sample).text_with_markdown_code_masked
            )
            is not None
        )
        negative_matches = sum(
            1
            for sample in negative_samples
            if _SLOP_WORD_RE.search(
                AnalysisDocument.from_text(sample).text_with_markdown_code_masked
            )
            is not None
        )
        return SlopWordRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            context_window_chars=self.config.context_window_chars,
        )
