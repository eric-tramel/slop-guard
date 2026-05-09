"""Detect throat-clearing phrases that delay the actual point.

Objective: Flag meta-framing constructions that announce something is about
to be said instead of just saying it (Zinsser: don't waste the first sentence
clearing your throat).

Example Rule Violations:
    - "It should be pointed out that the index is unused."
      Frames the claim instead of stating it.
    - "Truth be told, the migration regressed throughput."
      Performative honesty preface delays the actual finding.

Example Non-Violations:
    - "The index is unused."
      States the claim directly.
    - "The migration regressed throughput by 12%."
      Direct finding with a number.

Severity: Medium per hit; the framing always wastes attention.
"""

import re
from dataclasses import dataclass, field

from slop_guard.document import AnalysisDocument, context_around
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import fit_penalty_contrastive

_THROAT_CLEARING_PHRASES: tuple[str, ...] = (
    "it should be pointed out that",
    "the fact of the matter is",
    "truth be told",
    "it goes without saying that",
    "it is interesting to note that",
    "one might argue that",
    "as a matter of fact",
    "when all is said and done",
)
_THROAT_CLEARING_RE_LIST: tuple[re.Pattern[str], ...] = tuple(
    re.compile(re.escape(phrase), re.IGNORECASE) for phrase in _THROAT_CLEARING_PHRASES
)


@dataclass
class ThroatClearingRuleConfig(RuleConfig):
    """Config for throat-clearing phrase matching."""

    penalty: int = field(
        metadata={
            "description": ("Penalty applied per matched throat-clearing phrase.")
        }
    )
    context_window_chars: int = field(
        metadata={
            "description": (
                "Half-width (in characters) of the surrounding-text window "
                "captured as context for each throat-clearing violation."
            )
        }
    )


class ThroatClearingRule(Rule[ThroatClearingRuleConfig]):
    """Flag meta-framing phrases that delay the actual point."""

    name = "throat_clearing"
    count_key = "throat_clearing"
    level = RuleLevel.SENTENCE
    category = "writing_quality"

    def example_violations(self) -> list[str]:
        """Return samples that should trigger throat-clearing matches."""
        return [
            "It should be pointed out that the index is unused.",
            "Truth be told, the migration regressed throughput.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid throat-clearing matches."""
        return [
            "The index is unused.",
            "The migration regressed throughput by 12%.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Match each throat-clearing phrase and emit one violation per hit."""
        violations: list[Violation] = []
        seen: set[str] = set()
        advice_order: list[str] = []
        for pattern in _THROAT_CLEARING_RE_LIST:
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
            f"Cut '{phrase}' — state the claim directly." for phrase in advice_order
        ]
        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> ThroatClearingRuleConfig:
        """Fit penalty from throat-clearing prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def has_match(sample: str) -> bool:
            lower_text = sample.lower()
            return any(phrase in lower_text for phrase in _THROAT_CLEARING_PHRASES)

        positive_matches = sum(1 for sample in positive_samples if has_match(sample))
        negative_matches = sum(1 for sample in negative_samples if has_match(sample))
        return ThroatClearingRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            context_window_chars=self.config.context_window_chars,
        )
