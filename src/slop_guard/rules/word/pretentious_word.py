"""Detect pretentious vocabulary with concrete plain-English replacements.

Objective: Catch long words used where shorter ones do (Orwell's rule 2: never
use a long word where a short one will do). Each entry carries the replacement
so advice can recommend the specific substitution.

Example Rule Violations:
    - "We will utilize a new methodology."
      Uses "utilize" where "use" is shorter and clearer.
    - "Commence the aforementioned subsequent phase."
      Stacks pretentious replacements for "start", "this", and "next".

Example Non-Violations:
    - "Use the next phase of the rollout."
      Plain English equivalents.
    - "The method runs in O(n)."
      Domain term used precisely; no inflated synonym.

Severity: Medium per hit; the replacement is usually a strict improvement.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from slop_guard.document import AnalysisDocument, context_around
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import fit_penalty_contrastive

_PRETENTIOUS_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("utilize", "use"),
    ("utilizes", "uses"),
    ("utilized", "used"),
    ("utilizing", "using"),
    ("facilitate", "help"),
    ("facilitates", "helps"),
    ("facilitated", "helped"),
    ("facilitating", "helping"),
    ("commence", "start"),
    ("commences", "starts"),
    ("commenced", "started"),
    ("commencing", "starting"),
    ("subsequent", "next"),
    ("subsequently", "later"),
    ("methodology", "method"),
    ("methodologies", "methods"),
    ("ameliorate", "improve"),
    ("aforementioned", "this"),
    ("endeavor", "try"),
    ("endeavors", "tries"),
    ("endeavored", "tried"),
)
_PRETENTIOUS_BY_WORD: dict[str, str] = {
    word.lower(): replacement for word, replacement in _PRETENTIOUS_REPLACEMENTS
}
_PRETENTIOUS_RE = re.compile(
    r"\b(?:"
    + "|".join(re.escape(word) for word, _ in _PRETENTIOUS_REPLACEMENTS)
    + r")\b",
    re.IGNORECASE,
)


@dataclass
class PretentiousWordRuleConfig(RuleConfig):
    """Config for pretentious-word matching with replacements."""

    penalty: int = field(
        metadata={"description": ("Penalty applied per matched pretentious word.")}
    )
    context_window_chars: int = field(
        metadata={
            "description": (
                "Half-width (in characters) of the surrounding-text window "
                "captured as context for each pretentious-word violation."
            )
        }
    )


class PretentiousWordRule(Rule[PretentiousWordRuleConfig]):
    """Flag pretentious words and recommend the plain-English equivalent."""

    name = "pretentious_word"
    count_key = "pretentious_words"
    level = RuleLevel.WORD
    category = "writing_quality"

    def example_violations(self) -> list[str]:
        """Return samples that should trigger pretentious-word matches."""
        return [
            "We will utilize a new methodology.",
            "Commence the aforementioned phase.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid pretentious-word matches."""
        return [
            "Use the next phase of the rollout.",
            "The method runs in linear time.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Match each pretentious word and emit a replacement-aware violation."""
        masked_text = document.text_with_markdown_code_masked
        violations: list[Violation] = []
        word_counts: Counter[str] = Counter()
        advice_order: list[str] = []
        for match in _PRETENTIOUS_RE.finditer(masked_text):
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
                    start=match.start(),
                    end=match.end(),
                )
            )
            if word_counts[word] == 0:
                advice_order.append(word)
            word_counts[word] += 1

        if not violations:
            return RuleResult()

        advice = [
            f"Replace '{word}' with '{_PRETENTIOUS_BY_WORD[word]}'."
            for word in advice_order
        ]
        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> PretentiousWordRuleConfig:
        """Fit penalty strength from pretentious-word prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_matches = sum(
            1
            for sample in positive_samples
            if _PRETENTIOUS_RE.search(
                AnalysisDocument.from_text(sample).text_with_markdown_code_masked
            )
            is not None
        )
        negative_matches = sum(
            1
            for sample in negative_samples
            if _PRETENTIOUS_RE.search(
                AnalysisDocument.from_text(sample).text_with_markdown_code_masked
            )
            is not None
        )
        return PretentiousWordRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            context_window_chars=self.config.context_window_chars,
        )
