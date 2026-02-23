"""Sentence-level rule detecting unattributed weasel phrases."""

from __future__ import annotations

import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel

_WEASEL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsome critics argue\b", re.IGNORECASE),
    re.compile(r"\bmany believe\b", re.IGNORECASE),
    re.compile(r"\bexperts suggest\b", re.IGNORECASE),
    re.compile(r"\bstudies show\b", re.IGNORECASE),
    re.compile(r"\bsome argue\b", re.IGNORECASE),
    re.compile(r"\bit is widely believed\b", re.IGNORECASE),
    re.compile(r"\bresearch suggests\b", re.IGNORECASE),
)


@dataclass
class WeaselPhraseRuleConfig(RuleConfig):
    """Config for weasel phrase detection."""

    penalty: int
    context_window_chars: int


class WeaselPhraseRule(Rule[WeaselPhraseRuleConfig]):
    """Detect phrases that avoid concrete attribution."""

    name = "weasel"
    count_key = "weasel"
    level = RuleLevel.SENTENCE

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply weasel phrase regex checks."""
        violations: list[Violation] = []
        advice: list[str] = []
        count = 0

        for pattern in _WEASEL_PATTERNS:
            for match in pattern.finditer(document.text):
                phrase = match.group(0).lower()
                violations.append(
                    Violation(
                        rule=self.name,
                        match=phrase,
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
                    f"Cut '{phrase}' \u2014 either cite a source or own the claim."
                )
                count += 1

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: count} if count else {},
        )
