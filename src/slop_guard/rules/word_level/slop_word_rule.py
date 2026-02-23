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
_PLAIN_SLOP_WORDS: frozenset[str] = frozenset(
    word for word in _ALL_SLOP_WORDS if "-" not in word
)
_HYPHENATED_SLOP_WORDS: tuple[str, ...] = tuple(
    word for word in _ALL_SLOP_WORDS if "-" in word
)
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

        has_plain_slop_token = bool(document.word_token_set_lower & _PLAIN_SLOP_WORDS)
        has_hyphen_slop_fragment = any(
            word in document.lower_text for word in _HYPHENATED_SLOP_WORDS
        )
        if not has_plain_slop_token and not has_hyphen_slop_fragment:
            return RuleResult()

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
