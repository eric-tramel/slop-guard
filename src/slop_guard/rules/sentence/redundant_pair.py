"""Detect redundant word pairs where one word implies the other.

Objective: Flag stock phrases like "completely destroyed" or "end result"
where the modifier is already implicit in the other word.

Example Rule Violations:
    - "The cache was completely destroyed."
      "Destroyed" already implies completeness.
    - "We need to revert back to the previous schema."
      "Revert" already implies "back".

Example Non-Violations:
    - "The cache was destroyed."
      Single, sufficient verb.
    - "We need to revert to the previous schema."
      Concise form.

Severity: Low per hit; the redundant word is always a free deletion.
"""

import re
from dataclasses import dataclass, field

from slop_guard.document import AnalysisDocument, context_around
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import fit_penalty_contrastive

_REDUNDANT_PAIRS: tuple[str, ...] = (
    "completely destroyed",
    "totally unique",
    "absolutely essential",
    "end result",
    "final outcome",
    "past history",
    "future plans",
    "close proximity",
    "free gift",
    "advance warning",
    "advance planning",
    "true fact",
    "actual fact",
    "general consensus",
    "personal opinion",
    "revert back",
    "repeat again",
    "added bonus",
    "unexpected surprise",
    "exact same",
    "join together",
    "merge together",
    "combine together",
)
_REDUNDANT_PAIR_RE_LIST: tuple[re.Pattern[str], ...] = tuple(
    re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
    for phrase in _REDUNDANT_PAIRS
)


@dataclass
class RedundantPairRuleConfig(RuleConfig):
    """Config for redundant-pair phrase matching."""

    penalty: int = field(
        metadata={"description": ("Penalty applied per matched redundant phrase pair.")}
    )
    context_window_chars: int = field(
        metadata={
            "description": (
                "Half-width (in characters) of the surrounding-text window "
                "captured as context for each redundant-pair violation."
            )
        }
    )


class RedundantPairRule(Rule[RedundantPairRuleConfig]):
    """Flag pairs where one word is implied by the other."""

    name = "redundant_pair"
    count_key = "redundant_pairs"
    level = RuleLevel.SENTENCE
    category = "writing_quality"

    def example_violations(self) -> list[str]:
        """Return samples that should trigger redundant-pair matches."""
        return [
            "The cache was completely destroyed.",
            "We need to revert back to the previous schema.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid redundant-pair matches."""
        return [
            "The cache was destroyed.",
            "We need to revert to the previous schema.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Match each redundant pair and emit one violation per hit."""
        violations: list[Violation] = []
        seen: set[str] = set()
        advice_order: list[str] = []
        for pattern in _REDUNDANT_PAIR_RE_LIST:
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
                        start=match.start(),
                        end=match.end(),
                    )
                )
                if phrase not in seen:
                    advice_order.append(phrase)
                    seen.add(phrase)

        if not violations:
            return RuleResult()

        advice = [
            f"Cut '{phrase}' — keep one word; the other is implied."
            for phrase in advice_order
        ]
        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> RedundantPairRuleConfig:
        """Fit penalty from redundant-pair prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def has_match(sample: str) -> bool:
            lower_text = sample.lower()
            return any(phrase in lower_text for phrase in _REDUNDANT_PAIRS)

        positive_matches = sum(1 for sample in positive_samples if has_match(sample))
        negative_matches = sum(1 for sample in negative_samples if has_match(sample))
        return RedundantPairRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            context_window_chars=self.config.context_window_chars,
        )
