"""Detect weakening qualifier words and phrases.

Objective: Flag hedge qualifiers that drain specificity from claims (Twain:
substitute "damn" every time you write "very" and let your editor delete it).

Example Rule Violations:
    - "The fix is very fast and quite reliable."
      Stacks weakeners instead of citing concrete metrics.
    - "It was sort of unclear what the impact was."
      Uses a multi-word qualifier in place of a definite assessment.

Example Non-Violations:
    - "The patch reduced p99 latency from 400 ms to 90 ms."
      Concrete measurement with no hedging.
    - "Three retries succeeded; the fourth timed out."
      Direct statement of outcome.

Severity: Low per hit; cumulative penalty signals hedged or imprecise prose.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from slop_guard.document import AnalysisDocument, context_around
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import fit_penalty_contrastive

_QUALIFIER_TERMS: tuple[str, ...] = (
    "very",
    "quite",
    "rather",
    "somewhat",
    "fairly",
    "sort of",
    "kind of",
    "pretty much",
    "a bit",
)
_QUALIFIER_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in _QUALIFIER_TERMS) + r")\b",
    re.IGNORECASE,
)


@dataclass
class QualifierWordRuleConfig(RuleConfig):
    """Config for qualifier-word matching."""

    penalty: int = field(
        metadata={
            "description": ("Penalty applied per matched qualifier-word occurrence.")
        }
    )
    context_window_chars: int = field(
        metadata={
            "description": (
                "Half-width (in characters) of the surrounding-text window "
                "captured as context for each qualifier violation."
            )
        }
    )


class QualifierWordRule(Rule[QualifierWordRuleConfig]):
    """Record a violation per qualifier word or short qualifier phrase."""

    name = "qualifier_word"
    count_key = "qualifier_words"
    level = RuleLevel.WORD
    category = "writing_quality"

    def example_violations(self) -> list[str]:
        """Return samples that should trigger qualifier-word matches."""
        return [
            "The fix is very fast and quite reliable.",
            "It was sort of unclear what to do.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid qualifier-word matches."""
        return [
            "The patch reduced p99 latency from 400 ms to 90 ms.",
            "Three retries succeeded; the fourth timed out.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Match each qualifier occurrence and emit one violation per hit."""
        masked_text = document.text_with_markdown_code_masked
        violations: list[Violation] = []
        term_counts: Counter[str] = Counter()
        advice_order: list[str] = []
        for match in _QUALIFIER_RE.finditer(masked_text):
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
            f"Cut '{term}' — be specific or remove the qualifier."
            for term in advice_order
        ]
        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> QualifierWordRuleConfig:
        """Fit penalty strength from observed qualifier prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_matches = sum(
            1
            for sample in positive_samples
            if _QUALIFIER_RE.search(
                AnalysisDocument.from_text(sample).text_with_markdown_code_masked
            )
            is not None
        )
        negative_matches = sum(
            1
            for sample in negative_samples
            if _QUALIFIER_RE.search(
                AnalysisDocument.from_text(sample).text_with_markdown_code_masked
            )
            is not None
        )
        return QualifierWordRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            context_window_chars=self.config.context_window_chars,
        )
