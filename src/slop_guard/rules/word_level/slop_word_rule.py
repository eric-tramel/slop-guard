"""Word-level rule detecting overused AI-associated slop vocabulary."""

from __future__ import annotations

import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel

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
)

_SLOP_HEDGE = (
    "notably",
    "importantly",
    "furthermore",
    "additionally",
    "particularly",
    "significantly",
    "interestingly",
    "remarkably",
    "surprisingly",
    "fascinatingly",
    "moreover",
    "however",
    "overall",
)

_ALL_SLOP_WORDS = _SLOP_ADJECTIVES + _SLOP_VERBS + _SLOP_NOUNS + _SLOP_HEDGE
_SLOP_WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(word) for word in _ALL_SLOP_WORDS) + r")\b",
    re.IGNORECASE,
)


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

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply the slop-word detector to the full text."""
        violations: list[Violation] = []
        advice: list[str] = []
        count = 0

        for match in _SLOP_WORD_RE.finditer(document.text):
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
                )
            )
            advice.append(
                f"Replace '{word}' \u2014 what specifically do you mean?"
            )
            count += 1

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: count} if count else {},
        )
