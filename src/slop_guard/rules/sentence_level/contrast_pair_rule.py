"""Detect repeated contrast constructions that stage a binary opposition.

Objective: Identify overuse of rhetorical contrast patterns such as
"A, not B" and "not only X but Y"; repeated use can make prose feel
formulaic.

Example Rule Violations:
    - "This is focus, not frenzy."
      Uses the targeted "A, not B" shape.
    - "The platform is not only fast but also reliable."
      Uses the staged "not only X but Y" frame.

Example Non-Violations:
    - "This approach prioritizes focus over speed."
      Contrast exists, but not in the repetitive pattern form.
    - "The design reduces complexity while improving clarity."
      Balanced comparison without slogan-like structure.

Severity: Low per instance, medium when repeated frequently in one passage.
"""


import math
import re
from dataclasses import dataclass
from typing import Literal, TypeAlias

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import (
    clamp_int,
    fit_count_cap_contrastive,
    fit_penalty_contrastive,
    fit_threshold_high_contrastive,
    percentile_ceil,
)

_X_NOT_Y_RE = re.compile(r"\b(\w+), not (\w+)\b")
_STAGED_CONTRAST_RE = re.compile(
    r"\bnot (?:only|just|merely)\b"
    r"[^.!?\n]{1,80}?"
    r"\bbut(?: also)?\b"
    r"[^.!?\n,;:]{1,80}?"
    r"(?=[,.;:!?]|\n|$)",
    re.IGNORECASE,
)
ContrastMatchKind: TypeAlias = Literal["x_not_y", "staged_contrast"]
ContrastMatch: TypeAlias = tuple[ContrastMatchKind, int, int, str]


def _collect_contrast_matches(text: str) -> tuple[ContrastMatch, ...]:
    """Return ordered contrast matches detected in ``text``.

    Args:
        text: Source text to scan.

    Returns:
        Ordered match tuples containing match kind, character offsets, and the
        matched snippet.
    """
    matches: list[ContrastMatch] = []
    for match in _X_NOT_Y_RE.finditer(text):
        matches.append(("x_not_y", match.start(), match.end(), match.group(0)))
    for match in _STAGED_CONTRAST_RE.finditer(text):
        matches.append(
            ("staged_contrast", match.start(), match.end(), match.group(0).strip())
        )
    matches.sort(key=lambda item: (item[1], item[2], item[0]))
    return tuple(matches)


def _contrast_pair_advice(kind: ContrastMatchKind, snippet: str) -> str:
    """Return rewrite guidance for one contrast match.

    Args:
        kind: Match family used for the detection.
        snippet: Exact matched contrast snippet.

    Returns:
        A rewrite instruction tuned to the matched contrast form.
    """
    if kind == "x_not_y":
        return (
            f"Rewrite '{snippet}' as a plain sentence with the actual claim "
            "instead of an 'X, not Y' slogan."
        )
    return (
        f"Rewrite '{snippet}' as a direct sentence instead of staging it as "
        "a contrast."
    )


def _contrast_summary_advice(
    match_count: int,
    match_kinds: frozenset[ContrastMatchKind],
) -> str:
    """Return aggregate advice for repeated contrast matches.

    Args:
        match_count: Total number of detected contrast matches.
        match_kinds: Unique match families present in the source text.

    Returns:
        A summary advice line describing the repeated contrast usage.
    """
    if match_kinds == frozenset({"x_not_y"}):
        return (
            f"{match_count} 'X, not Y' contrasts \u2014 stop stacking slogan-like "
            "oppositions; rewrite at least one as a plain sentence with the actual "
            "tradeoff."
        )
    return (
        f"{match_count} contrast constructions \u2014 stop stacking staged "
        "oppositions; rewrite at least one as a plain sentence with the actual "
        "tradeoff."
    )


@dataclass
class ContrastPairRuleConfig(RuleConfig):
    """Config for contrast pair detection and recording limits."""

    penalty: int
    record_cap: int
    advice_min: int
    context_window_chars: int


class ContrastPairRule(Rule[ContrastPairRuleConfig]):
    """Detect repeated binary-opposition contrast constructions."""

    name = "contrast_pair"
    count_key = "contrast_pairs"
    level = RuleLevel.SENTENCE

    def example_violations(self) -> list[str]:
        """Return samples that should trigger contrast-pair matches."""
        return [
            "This is focus, not frenzy.",
            "The platform is not only fast but also reliable.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid contrast-pair matches."""
        return [
            "This approach prioritizes focus over speed.",
            "The design reduces complexity while improving clarity.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply contrast detection and aggregate advice."""
        matches = _collect_contrast_matches(document.text)
        violations: list[Violation] = []
        advice: list[str] = []

        for kind, start, end, snippet in matches[: self.config.record_cap]:
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
                )
            )
            advice.append(_contrast_pair_advice(kind, snippet))

        if len(matches) >= self.config.advice_min:
            advice.append(
                _contrast_summary_advice(
                    len(matches),
                    frozenset(kind for kind, *_rest in matches),
                )
            )

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)} if violations else {},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> ContrastPairRuleConfig:
        """Fit match-driven caps and penalties from corpus counts."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_counts = [
            len(_collect_contrast_matches(sample)) for sample in positive_samples
        ]
        negative_counts = [
            len(_collect_contrast_matches(sample)) for sample in negative_samples
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

        return ContrastPairRuleConfig(
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
