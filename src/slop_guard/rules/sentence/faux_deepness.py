"""Detect faux-deep negations of ordinary metaphorical predicates.

Objective: Catch prose that tries to sound profound by denying familiar
metaphors, usually in stacked sentences such as "Silence does not settle" or
"A truth does not land."

Example Rule Violations:
    - "Silence does not "settle"."
      Negates an ordinary metaphor for an abstract subject.
    - "Words do not hang in the air. History does not press."
      Stacks multiple abstract negations as a depth effect.

Example Non-Violations:
    - "The paint does not settle evenly in cold rooms."
      Concrete subject and concrete predicate use.
    - "The team waited in silence while the room settled."
      Uses the metaphor directly instead of denying it for effect.

Severity: Low per sentence, medium when repeated in one passage.

Notes: This is a precision-biased pattern rule, not semantic analysis. It
requires an abstract subject and either a short quoted predicate or a known
metaphorical predicate from the offline lexicon.
"""

import math
import re
from dataclasses import dataclass, field
from typing import TypeAlias

from slop_guard.document import AnalysisDocument, context_around
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import (
    clamp_int,
    fit_count_cap_contrastive,
    fit_penalty_contrastive,
    fit_threshold_high_contrastive,
    percentile_ceil,
)

_ABSTRACT_SUBJECTS: tuple[str, ...] = (
    "absence",
    "beauty",
    "belief",
    "belonging",
    "certainty",
    "chaos",
    "clarity",
    "conscience",
    "death",
    "desire",
    "doubt",
    "faith",
    "fear",
    "grief",
    "history",
    "hope",
    "identity",
    "knowledge",
    "language",
    "loneliness",
    "love",
    "memory",
    "meaning",
    "mercy",
    "pain",
    "presence",
    "regret",
    "silence",
    "time",
    "truth",
    "truths",
    "violence",
    "words",
    "wound",
    "wounds",
)
_METAPHOR_PREDICATES: tuple[str, ...] = (
    "ache",
    "aches",
    "arrive",
    "arrives",
    "bleed",
    "bleeds",
    "bloom",
    "blooms",
    "breathe",
    "breathes",
    "burn",
    "burns",
    "carry",
    "carries",
    "close",
    "closes",
    "drift",
    "drifts",
    "echo",
    "echoes",
    "float",
    "floats",
    "hang",
    "hang in the air",
    "hangs",
    "hangs in the air",
    "haunt",
    "haunts",
    "hold",
    "holds",
    "land",
    "lands",
    "move",
    "moves",
    "open",
    "opens",
    "press",
    "presses",
    "remember",
    "remembers",
    "settle",
    "settles",
    "sing",
    "sings",
    "sit",
    "sit in the room",
    "sits",
    "sits in the room",
    "sleep",
    "sleeps",
    "speak",
    "speaks",
    "stare back",
    "stares back",
    "wait",
    "waits",
    "whisper",
    "whispers",
)
_METAPHOR_HEADS: frozenset[str] = frozenset(
    predicate.split()[0] for predicate in _METAPHOR_PREDICATES
)
_SUBJECT_ALT = "|".join(re.escape(subject) for subject in _ABSTRACT_SUBJECTS)
_PREDICATE_ALT = "|".join(
    re.escape(predicate).replace(r"\ ", r"\s+")
    for predicate in sorted(
        _METAPHOR_PREDICATES,
        key=lambda predicate: len(predicate),
        reverse=True,
    )
)
_DETERMINER_RE = (
    r"(?:(?:a|an|the|this|that|these|those|our|their|its|his|her|my|your)\s+)?"
)
_SUBJECT_RE = rf"{_DETERMINER_RE}(?:[a-z][a-z'-]*\s+){{0,2}}(?:{_SUBJECT_ALT})"
_NEGATION_RE = (
    r"(?:"
    r"(?:does|do|did|can|could|will|would|should)\s+not|"
    r"doesn't|don't|didn't|cannot|can't|won't|wouldn't|shouldn't|never"
    r")"
)
_QUOTED_PREDICATE_RE = re.compile(
    rf"(?<!\w)(?P<subject>{_SUBJECT_RE})\s+"
    rf"(?P<negation>{_NEGATION_RE})\s+"
    r"(?P<quote>[\"'“‘])(?P<predicate>[A-Za-z][A-Za-z\s'.,-]{0,80}?)[\"'”’]",
    re.IGNORECASE,
)
_UNQUOTED_PREDICATE_RE = re.compile(
    rf"(?<!\w)(?P<subject>{_SUBJECT_RE})\s+"
    rf"(?P<negation>{_NEGATION_RE})\s+"
    rf"(?P<predicate>{_PREDICATE_ALT})(?=\b|[.!?,;:])",
    re.IGNORECASE,
)

FauxDeepnessMatch: TypeAlias = tuple[int, int, str]


def _normalize_predicate(predicate: str) -> str:
    """Return a lowercase predicate with quote punctuation stripped.

    Args:
        predicate: Raw predicate text captured after a negated auxiliary.

    Returns:
        A whitespace-normalized predicate string.
    """
    stripped = predicate.strip(" \t\r\n\"'“”‘’.,;:!?")
    return " ".join(stripped.casefold().split())


def _looks_like_metaphor_predicate(predicate: str) -> bool:
    """Return whether a quoted predicate belongs to the metaphor lexicon.

    Args:
        predicate: Raw predicate text inside quote marks.

    Returns:
        ``True`` when the predicate is a known phrase or starts with a known
        metaphor head verb.
    """
    normalized = _normalize_predicate(predicate)
    if normalized in _METAPHOR_PREDICATES:
        return True
    first_word = normalized.split(" ", 1)[0] if normalized else ""
    return first_word in _METAPHOR_HEADS


def _collect_faux_deepness_matches(text: str) -> tuple[FauxDeepnessMatch, ...]:
    """Return ordered faux-deepness matches detected in ``text``.

    Args:
        text: Source text to scan, usually with Markdown code spans masked.

    Returns:
        Ordered match tuples containing character offsets and matched snippets.
    """
    matches: list[FauxDeepnessMatch] = []
    seen_spans: set[tuple[int, int]] = set()

    for match in _QUOTED_PREDICATE_RE.finditer(text):
        if not _looks_like_metaphor_predicate(match.group("predicate")):
            continue
        span = (match.start(), match.end())
        seen_spans.add(span)
        matches.append((span[0], span[1], match.group(0).strip()))

    for match in _UNQUOTED_PREDICATE_RE.finditer(text):
        span = (match.start(), match.end())
        if span in seen_spans:
            continue
        matches.append((span[0], span[1], match.group(0).strip()))

    matches.sort(key=lambda item: (item[0], item[1], item[2]))
    return tuple(matches)


def _faux_deepness_advice(snippet: str) -> str:
    """Return rewrite guidance for one faux-deepness match.

    Args:
        snippet: Exact matched negation snippet.

    Returns:
        A rewrite instruction for the matched pattern.
    """
    return (
        f"Rewrite '{snippet}' as the concrete claim; do not deny a familiar "
        "metaphor to create depth."
    )


def _faux_deepness_summary_advice(match_count: int) -> str:
    """Return aggregate advice for repeated faux-deepness matches.

    Args:
        match_count: Total number of detected faux-deepness matches.

    Returns:
        A summary advice line for a repeated pattern.
    """
    return (
        f"{match_count} faux-deepness negations - stop stacking abstract "
        "subjects with denied metaphors; replace at least one with a concrete "
        "claim."
    )


@dataclass
class FauxDeepnessRuleConfig(RuleConfig):
    """Config for faux-deepness detection and recording limits."""

    penalty: int = field(
        metadata={
            "description": (
                "Penalty applied per recorded abstract negation of a familiar "
                "metaphorical predicate."
            )
        }
    )
    record_cap: int = field(
        metadata={
            "description": (
                "Maximum number of faux-deepness matches recorded as "
                "individual violations in a single pass."
            )
        }
    )
    advice_min: int = field(
        metadata={
            "description": (
                "Threshold on the total faux-deepness match count at or above "
                "which a summary advice line is emitted."
            )
        }
    )
    context_window_chars: int = field(
        metadata={
            "description": (
                "Half-width (in characters) of the surrounding-text window "
                "captured as context for each faux-deepness violation."
            )
        }
    )


class FauxDeepnessRule(Rule[FauxDeepnessRuleConfig]):
    """Detect negated metaphorical abstractions posing as depth."""

    name = "faux_deepness"
    count_key = "faux_deepness"
    level = RuleLevel.SENTENCE

    def example_violations(self) -> list[str]:
        """Return samples that should trigger faux-deepness matches."""
        return [
            'Silence does not "settle".',
            "Words do not hang in the air. History does not press.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid faux-deepness matches."""
        return [
            "The paint does not settle evenly in cold rooms.",
            "The team waited in silence while the room settled.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply faux-deepness detection and aggregate advice."""
        matches = _collect_faux_deepness_matches(
            document.text_with_markdown_code_masked
        )
        violations: list[Violation] = []
        advice: list[str] = []

        for start, end, _masked_snippet in matches[: self.config.record_cap]:
            snippet = document.text[start:end].strip()
            violations.append(
                Violation(
                    rule=self.name,
                    match=snippet,
                    context=context_around(
                        document.text,
                        start,
                        end,
                        width=self.config.context_window_chars,
                    ),
                    penalty=self.config.penalty,
                    start=start,
                    end=end,
                )
            )
            advice.append(_faux_deepness_advice(snippet))

        if len(matches) >= self.config.advice_min:
            advice.append(_faux_deepness_summary_advice(len(matches)))

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)} if violations else {},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> FauxDeepnessRuleConfig:
        """Fit match-driven caps and penalties from corpus counts."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_counts = [
            len(_collect_faux_deepness_matches(sample)) for sample in positive_samples
        ]
        negative_counts = [
            len(_collect_faux_deepness_matches(sample)) for sample in negative_samples
        ]
        positive_matches = sum(1 for count in positive_counts if count > 0)
        negative_matches = sum(1 for count in negative_counts if count > 0)
        positive_nonzero_counts = [count for count in positive_counts if count > 0]
        negative_nonzero_counts = [count for count in negative_counts if count > 0]

        record_cap = fit_count_cap_contrastive(
            default_value=clamp_int(
                percentile_ceil(positive_nonzero_counts, 0.90), 1, 64
            )
            if positive_nonzero_counts
            else self.config.record_cap,
            positive_values=positive_nonzero_counts,
            negative_values=negative_nonzero_counts,
            lower=1,
            upper=64,
            positive_quantile=0.90,
            negative_quantile=0.90,
            blend_pivot=20.0,
        )
        advice_min = clamp_int(
            math.ceil(
                fit_threshold_high_contrastive(
                    default_value=float(
                        clamp_int(percentile_ceil(positive_counts, 0.75), 1, 64)
                    ),
                    positive_values=positive_counts,
                    negative_values=negative_counts,
                    lower=1.0,
                    upper=64.0,
                    positive_quantile=0.75,
                    negative_quantile=0.25,
                    blend_pivot=16.0,
                    match_mode="ge",
                )
            ),
            1,
            64,
        )

        return FauxDeepnessRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            record_cap=record_cap,
            advice_min=advice_min,
            context_window_chars=self.config.context_window_chars,
        )
