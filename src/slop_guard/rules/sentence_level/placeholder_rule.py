"""Sentence-level rule detecting unfinished placeholder markers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel

_PLACEHOLDER_RE = re.compile(
    r"\[insert [^\]]*\]|\[describe [^\]]*\]|\[url [^\]]*\]|\[your [^\]]*\]|\[todo[^\]]*\]",
    re.IGNORECASE,
)


@dataclass
class PlaceholderRuleConfig(RuleConfig):
    """Config for placeholder text detection."""

    penalty: int
    context_window_chars: int


class PlaceholderRule(Rule[PlaceholderRuleConfig]):
    """Detect bracketed placeholders that indicate unfinished drafts."""

    name = "placeholder"
    count_key = "placeholder"
    level = RuleLevel.SENTENCE

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply placeholder regex checks to the text."""
        violations: list[Violation] = []
        advice: list[str] = []
        count = 0

        for match in _PLACEHOLDER_RE.finditer(document.text):
            value = match.group(0).lower()
            violations.append(
                Violation(
                    rule=self.name,
                    match=value,
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
                f"Remove placeholder '{value}' \u2014 this is unfinished template text."
            )
            count += 1

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: count} if count else {},
        )
