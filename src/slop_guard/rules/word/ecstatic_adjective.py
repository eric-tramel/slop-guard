"""Detect vague high-praise adjectives.

Objective: Flag promotional adjectives that vague over the concrete property
they're praising. "What makes it 'amazing'? Replace with specifics."

Example Rule Violations:
    - "This is a wonderful, fantastic, mind-blowing release."
      Stacked vague praise instead of any concrete property.
    - "An amazing improvement in throughput."
      Praise without a number or named property.

Example Non-Violations:
    - "Throughput rose 3.4x at the same p99 budget."
      Concrete metric replaces the praise.
    - "The release closed 12 long-standing data corruption bugs."
      Names what changed without rhetorical inflation.

Severity: Low per hit; cumulative use signals promotional rather than reported
prose. Skips entries already covered by SlopWordRule (stunning, breathtaking,
captivating).
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from slop_guard.document import AnalysisDocument, context_around
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import fit_penalty_contrastive

_ECSTATIC_TERMS: tuple[str, ...] = (
    "wonderful",
    "amazing",
    "incredible",
    "fantastic",
    "phenomenal",
    "magnificent",
    "mind-blowing",
    "awe-inspiring",
)
_ECSTATIC_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in _ECSTATIC_TERMS) + r")\b",
    re.IGNORECASE,
)


@dataclass
class EcstaticAdjectiveRuleConfig(RuleConfig):
    """Config for ecstatic-adjective matching."""

    penalty: int = field(
        metadata={"description": ("Penalty applied per matched ecstatic adjective.")}
    )
    context_window_chars: int = field(
        metadata={
            "description": (
                "Half-width (in characters) of the surrounding-text window "
                "captured as context for each ecstatic-adjective violation."
            )
        }
    )


class EcstaticAdjectiveRule(Rule[EcstaticAdjectiveRuleConfig]):
    """Record one violation per ecstatic high-praise adjective."""

    name = "ecstatic_adjective"
    count_key = "ecstatic_adjectives"
    level = RuleLevel.WORD
    category = "writing_quality"

    def example_violations(self) -> list[str]:
        """Return samples that should trigger ecstatic-adjective matches."""
        return [
            "This is a wonderful and fantastic release.",
            "The result was mind-blowing.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid ecstatic-adjective matches."""
        return [
            "Throughput rose 3.4x at the same p99 budget.",
            "The release closed 12 data corruption bugs.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Match each ecstatic adjective and emit one violation per hit."""
        masked_text = document.text_with_markdown_code_masked
        violations: list[Violation] = []
        term_counts: Counter[str] = Counter()
        advice_order: list[str] = []
        for match in _ECSTATIC_RE.finditer(masked_text):
            term = match.group(0).lower()
            violations.append(
                Violation(
                    rule=self.name,
                    match=term,
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
            if term_counts[term] == 0:
                advice_order.append(term)
            term_counts[term] += 1

        if not violations:
            return RuleResult()

        advice = [
            f"Cut '{term}' — name the concrete property, metric, or change."
            for term in advice_order
        ]
        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> EcstaticAdjectiveRuleConfig:
        """Fit penalty strength from observed ecstatic-adjective prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_matches = sum(
            1
            for sample in positive_samples
            if _ECSTATIC_RE.search(
                AnalysisDocument.from_text(sample).text_with_markdown_code_masked
            )
            is not None
        )
        negative_matches = sum(
            1
            for sample in negative_samples
            if _ECSTATIC_RE.search(
                AnalysisDocument.from_text(sample).text_with_markdown_code_masked
            )
            is not None
        )
        return EcstaticAdjectiveRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            context_window_chars=self.config.context_window_chars,
        )
