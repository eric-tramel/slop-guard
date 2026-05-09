"""Detect over-explanation phrases that announce the obvious.

Objective: Flag prefaces that label what follows as self-evident. If it is
obvious you don't need to say so; if it isn't, saying "obviously" won't fix it.

Example Rule Violations:
    - "Needless to say, retries should be idempotent."
      Announces obviousness instead of just stating the rule.
    - "It is obvious that the cache hit rate matters."
      Same pattern, longer.

Example Non-Violations:
    - "Retries should be idempotent."
      Direct statement.
    - "Cache hit rate dropped from 92% to 41%."
      Concrete claim with a number.

Severity: Medium per hit; almost always replaceable with the bare claim.
"""

import re
from dataclasses import dataclass, field

from slop_guard.document import AnalysisDocument, context_around
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import fit_penalty_contrastive

_OVER_EXPLANATION_PHRASES: tuple[str, ...] = (
    "needless to say",
    "as everyone knows",
    "it is obvious that",
    "it goes without saying",
    "as you can see",
    "as we all know",
)
_OVER_EXPLANATION_RE_LIST: tuple[re.Pattern[str], ...] = tuple(
    re.compile(re.escape(phrase), re.IGNORECASE) for phrase in _OVER_EXPLANATION_PHRASES
)


@dataclass
class OverExplanationRuleConfig(RuleConfig):
    """Config for over-explanation phrase matching."""

    penalty: int = field(
        metadata={
            "description": ("Penalty applied per matched over-explanation phrase.")
        }
    )
    context_window_chars: int = field(
        metadata={
            "description": (
                "Half-width (in characters) of the surrounding-text window "
                "captured as context for each over-explanation violation."
            )
        }
    )


class OverExplanationRule(Rule[OverExplanationRuleConfig]):
    """Flag prefaces that announce what follows is self-evident."""

    name = "over_explanation"
    count_key = "over_explanation"
    level = RuleLevel.SENTENCE
    category = "writing_quality"

    def example_violations(self) -> list[str]:
        """Return samples that should trigger over-explanation matches."""
        return [
            "Needless to say, retries should be idempotent.",
            "It is obvious that the cache hit rate matters.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid over-explanation matches."""
        return [
            "Retries should be idempotent.",
            "Cache hit rate dropped from 92% to 41%.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Match each over-explanation phrase and emit one violation per hit."""
        violations: list[Violation] = []
        seen: set[str] = set()
        advice_order: list[str] = []
        for pattern in _OVER_EXPLANATION_RE_LIST:
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
            f"Cut '{phrase}' — state the claim without prefacing it as obvious."
            for phrase in advice_order
        ]
        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> OverExplanationRuleConfig:
        """Fit penalty from over-explanation prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def has_match(sample: str) -> bool:
            lower_text = sample.lower()
            return any(phrase in lower_text for phrase in _OVER_EXPLANATION_PHRASES)

        positive_matches = sum(1 for sample in positive_samples if has_match(sample))
        negative_matches = sum(1 for sample in negative_samples if has_match(sample))
        return OverExplanationRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            context_window_chars=self.config.context_window_chars,
        )
