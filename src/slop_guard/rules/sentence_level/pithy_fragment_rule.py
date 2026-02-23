"""Sentence-level rule detecting short evaluative pivot fragments."""

from __future__ import annotations

import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel

_PITHY_PIVOT_RE = re.compile(r",\s+(?:but|yet|and|not|or)\b", re.IGNORECASE)


@dataclass
class PithyFragmentRuleConfig(RuleConfig):
    """Config for pithy fragment thresholds."""

    penalty: int
    max_sentence_words: int
    record_cap: int


class PithyFragmentRule(Rule[PithyFragmentRuleConfig]):
    """Detect short sentence fragments that pivot evaluatively."""

    name = "pithy_fragment"
    count_key = "pithy_fragment"
    level = RuleLevel.SENTENCE

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Scan sentence list for pithy pivot signatures."""
        violations: list[Violation] = []
        advice: list[str] = []
        count = 0

        for sentence in document.sentences:
            sentence_text = sentence.strip()
            if not sentence_text:
                continue
            if len(sentence_text.split()) > self.config.max_sentence_words:
                continue
            if _PITHY_PIVOT_RE.search(sentence_text) is None:
                continue

            if count < self.config.record_cap:
                violations.append(
                    Violation(
                        rule=self.name,
                        match=sentence_text,
                        context=sentence_text,
                        penalty=self.config.penalty,
                    )
                )
                advice.append(
                    f"'{sentence_text}' \u2014 pithy evaluative fragments are a Claude tell. "
                    "Expand or cut."
                )
            count += 1

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: count} if count else {},
        )
