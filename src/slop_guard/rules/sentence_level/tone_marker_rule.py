"""Detect AI-style tone markers and opener tells.

Objective: Flag conversational control phrases and stylized sentence openers
that often reveal model voice (meta guidance, scripted narrativity, and
formulaic certainty openers).

Example Rule Violations:
    - "Would you like me to provide a shorter version?"
      Meta-conversation phrasing is an AI tell in authored prose.
    - "Certainly, this approach works in most environments."
      Formulaic opener pattern used by assistant responses.

Example Non-Violations:
    - "This approach works in most environments."
      Same claim without assistant-style framing.
    - "The failure occurred after the second retry."
      Neutral narration without scripted dramatic setup.

Severity: Medium to high; often a strong signal of assistant-authored tone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel

_META_COMM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"would you like", re.IGNORECASE),
    re.compile(r"let me know if", re.IGNORECASE),
    re.compile(r"as mentioned", re.IGNORECASE),
    re.compile(r"i hope this", re.IGNORECASE),
    re.compile(r"feel free to", re.IGNORECASE),
    re.compile(r"don't hesitate to", re.IGNORECASE),
)

_FALSE_NARRATIVITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"then something interesting happened", re.IGNORECASE),
    re.compile(r"this is where things get interesting", re.IGNORECASE),
    re.compile(r"that's when everything changed", re.IGNORECASE),
)

_SENTENCE_OPENER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:^|[.!?]\s+)(certainly[,! ])", re.IGNORECASE | re.MULTILINE),
    re.compile(r"(?:^|[.!?]\s+)(absolutely[,! ])", re.IGNORECASE | re.MULTILINE),
)


@dataclass
class ToneMarkerRuleConfig(RuleConfig):
    """Config for tone marker pattern matching."""

    tone_penalty: int
    sentence_opener_penalty: int
    context_window_chars: int


class ToneMarkerRule(Rule[ToneMarkerRuleConfig]):
    """Detect direct AI-style tone markers and sentence opener tells."""

    name = "tone"
    count_key = "tone"
    level = RuleLevel.SENTENCE

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply tone marker checks to full text."""
        violations: list[Violation] = []
        advice: list[str] = []
        count = 0

        for pattern in _META_COMM_PATTERNS:
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
                        penalty=self.config.tone_penalty,
                    )
                )
                advice.append(
                    f"Remove '{phrase}' \u2014 this is a direct AI tell."
                )
                count += 1

        for pattern in _FALSE_NARRATIVITY_PATTERNS:
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
                        penalty=self.config.tone_penalty,
                    )
                )
                advice.append(
                    f"Cut '{phrase}' \u2014 announce less, show more."
                )
                count += 1

        for pattern in _SENTENCE_OPENER_PATTERNS:
            for match in pattern.finditer(document.text):
                word = match.group(1).strip(" ,!").lower()
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
                        penalty=self.config.sentence_opener_penalty,
                    )
                )
                advice.append(
                    f"'{word}' as a sentence opener is an AI tell \u2014 just make the point."
                )
                count += 1

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: count} if count else {},
        )
