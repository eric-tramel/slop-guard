"""Detect repeated "X, not Y" contrast constructions.

Objective: Identify overuse of a specific rhetorical pattern where contrast is
presented as "A, not B"; repeated use can make prose feel formulaic.

Example Rule Violations:
    - "This is focus, not frenzy."
      Uses the targeted contrast shape.
    - "It is clarity, not complexity."
      Repeats the same sentence skeleton as a style tic.

Example Non-Violations:
    - "This approach prioritizes focus over speed."
      Contrast exists, but not in the repetitive pattern form.
    - "The design reduces complexity while improving clarity."
      Balanced comparison without slogan-like structure.

Severity: Low per instance, medium when repeated frequently in one passage.
"""


import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel

_CONTRAST_PAIR_RE = re.compile(r"\b(\w+), not (\w+)\b")


@dataclass
class ContrastPairRuleConfig(RuleConfig):
    """Config for contrast pair detection and recording limits."""

    penalty: int
    record_cap: int
    advice_min: int
    context_window_chars: int


class ContrastPairRule(Rule[ContrastPairRuleConfig]):
    """Detect the Claude-style "X, not Y" rhetorical construction."""

    name = "contrast_pair"
    count_key = "contrast_pairs"
    level = RuleLevel.SENTENCE

    def example_violations(self) -> list[str]:
        """Return samples that should trigger contrast-pair matches."""
        return [
            "This is focus, not frenzy.",
            "It is clarity, not complexity.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid contrast-pair matches."""
        return [
            "This approach prioritizes focus over speed.",
            "The design reduces complexity while improving clarity.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply contrast detection and aggregate advice."""
        matches = list(_CONTRAST_PAIR_RE.finditer(document.text))
        violations: list[Violation] = []
        advice: list[str] = []

        for match in matches[: self.config.record_cap]:
            snippet = match.group(0)
            violations.append(
                Violation(
                    rule=self.name,
                    match=snippet,
                    context=context_around(
                        document.text,
                        match.start(),
                        match.end(),
                        width=self.config.context_window_chars,
                    ),
                    penalty=self.config.penalty,
                )
            )
            advice.append(
                f"'{snippet}' \u2014 'X, not Y' contrast \u2014 consider rephrasing to avoid the Claude pattern."
            )

        if len(matches) >= self.config.advice_min:
            advice.append(
                f"{len(matches)} 'X, not Y' contrasts \u2014 this is a Claude rhetorical tic. "
                "Vary your phrasing."
            )

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)} if violations else {},
        )
