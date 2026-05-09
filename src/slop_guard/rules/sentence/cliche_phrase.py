"""Detect worn metaphorical clichés.

Objective: Flag idioms whose figurative force has been worn out (Orwell:
never use a metaphor you're accustomed to seeing in print).

Example Rule Violations:
    - "Let's think outside the box and move the needle."
      Stacks two corporate clichés in one breath.
    - "The cache hit rate is just the tip of the iceberg."
      Reaches for a cliché instead of naming the underlying issue.

Example Non-Violations:
    - "We can reduce p99 by batching writes; cache misses dominate the rest."
      Concrete causes named directly.
    - "The lock contention pattern repeats across three subsystems."
      Specific observation without metaphor.

Severity: Medium per hit; clichés rarely add information their replacement
sentence cannot.
"""

import re
from dataclasses import dataclass, field

from slop_guard.document import AnalysisDocument, context_around
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import fit_penalty_contrastive

_CLICHE_PHRASES: tuple[str, ...] = (
    "think outside the box",
    "low-hanging fruit",
    "move the needle",
    "tip of the iceberg",
    "elephant in the room",
    "perfect storm",
    "silver bullet",
    "double-edged sword",
    "hit the ground running",
    "reinvent the wheel",
    "boil the ocean",
    "circle back",
    "drink the kool-aid",
    "raise the bar",
    "push the envelope",
    "best of breed",
    "win-win",
    "synergy",
    "core competency",
    "paradigm shift",
)
_CLICHE_RE_LIST: tuple[re.Pattern[str], ...] = tuple(
    re.compile(re.escape(phrase), re.IGNORECASE) for phrase in _CLICHE_PHRASES
)


@dataclass
class ClichePhraseRuleConfig(RuleConfig):
    """Config for cliché-phrase matching."""

    penalty: int = field(
        metadata={"description": ("Penalty applied per matched cliché phrase.")}
    )
    context_window_chars: int = field(
        metadata={
            "description": (
                "Half-width (in characters) of the surrounding-text window "
                "captured as context for each cliché violation."
            )
        }
    )


class ClichePhraseRule(Rule[ClichePhraseRuleConfig]):
    """Flag worn metaphors whose figurative force has eroded."""

    name = "cliche_phrase"
    count_key = "cliche_phrases"
    level = RuleLevel.SENTENCE
    category = "writing_quality"

    def example_violations(self) -> list[str]:
        """Return samples that should trigger cliché matches."""
        return [
            "Let's think outside the box and move the needle.",
            "The cache hit rate is just the tip of the iceberg.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid cliché matches."""
        return [
            "We can reduce p99 by batching writes.",
            "Lock contention repeats across three subsystems.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Match each cliché and emit one violation per hit."""
        violations: list[Violation] = []
        seen: set[str] = set()
        advice_order: list[str] = []
        for pattern in _CLICHE_RE_LIST:
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
            f"Cut '{phrase}' — name the concrete idea the cliché stands in for."
            for phrase in advice_order
        ]
        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> ClichePhraseRuleConfig:
        """Fit penalty from cliché prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def has_match(sample: str) -> bool:
            lower_text = sample.lower()
            return any(phrase in lower_text for phrase in _CLICHE_PHRASES)

        positive_matches = sum(1 for sample in positive_samples if has_match(sample))
        negative_matches = sum(1 for sample in negative_samples if has_match(sample))
        return ClichePhraseRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            context_window_chars=self.config.context_window_chars,
        )
