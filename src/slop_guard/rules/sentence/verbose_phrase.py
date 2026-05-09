"""Detect wordy phrases with shorter equivalents.

Objective: Flag verbose constructions and recommend the concise replacement
(Strunk & White: omit needless words). Each entry pairs the wordy phrase with
its plain-English substitute.

Example Rule Violations:
    - "We migrated in order to reduce cost."
      Uses "in order to" where "to" suffices.
    - "Due to the fact that the disk was full, writes failed."
      Uses "due to the fact that" where "because" suffices.

Example Non-Violations:
    - "We migrated to reduce cost."
      Uses the concise form already.
    - "Writes failed because the disk was full."
      Uses "because" directly.

Severity: Medium per hit; replacements are deterministic and unambiguous.
"""

import re
from dataclasses import dataclass, field

from slop_guard.document import AnalysisDocument, context_around
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import fit_penalty_contrastive

_VERBOSE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("in order to", "to"),
    ("due to the fact that", "because"),
    ("at the present time", "now"),
    ("at this point in time", "now"),
    ("has the ability to", "can"),
    ("have the ability to", "can"),
    ("the vast majority of", "most"),
    ("a large number of", "many"),
    ("a small number of", "a few"),
    ("whether or not", "whether"),
    ("for the purpose of", "for"),
    ("with regard to", "about"),
    ("with respect to", "about"),
    ("in the event that", "if"),
    ("in spite of the fact that", "although"),
    ("on a regular basis", "regularly"),
    ("in close proximity to", "near"),
    ("at a later date", "later"),
    ("prior to", "before"),
    ("subsequent to", "after"),
)
_VERBOSE_BY_PHRASE: dict[str, str] = {
    phrase.lower(): replacement for phrase, replacement in _VERBOSE_REPLACEMENTS
}
_VERBOSE_RE_LIST: tuple[re.Pattern[str], ...] = tuple(
    re.compile(re.escape(phrase), re.IGNORECASE) for phrase, _ in _VERBOSE_REPLACEMENTS
)


@dataclass
class VerbosePhraseRuleConfig(RuleConfig):
    """Config for verbose-phrase matching with replacements."""

    penalty: int = field(
        metadata={"description": ("Penalty applied per matched verbose phrase.")}
    )
    context_window_chars: int = field(
        metadata={
            "description": (
                "Half-width (in characters) of the surrounding-text window "
                "captured as context for each verbose-phrase violation."
            )
        }
    )


class VerbosePhraseRule(Rule[VerbosePhraseRuleConfig]):
    """Flag verbose phrases and recommend the concise replacement."""

    name = "verbose_phrase"
    count_key = "verbose_phrases"
    level = RuleLevel.SENTENCE
    category = "writing_quality"

    def example_violations(self) -> list[str]:
        """Return samples that should trigger verbose-phrase matches."""
        return [
            "We migrated in order to reduce cost.",
            "Due to the fact that the disk was full, writes failed.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid verbose-phrase matches."""
        return [
            "We migrated to reduce cost.",
            "Writes failed because the disk was full.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Match each verbose phrase and emit a replacement-aware violation."""
        violations: list[Violation] = []
        seen_phrases: set[str] = set()
        advice_order: list[str] = []
        for pattern in _VERBOSE_RE_LIST:
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
                if phrase not in seen_phrases:
                    advice_order.append(phrase)
                    seen_phrases.add(phrase)

        if not violations:
            return RuleResult()

        advice = [
            f"Replace '{phrase}' with '{_VERBOSE_BY_PHRASE[phrase]}'."
            for phrase in advice_order
        ]
        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> VerbosePhraseRuleConfig:
        """Fit penalty from verbose-phrase prevalence in the fit corpus."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def has_match(sample: str) -> bool:
            lower_text = sample.lower()
            return any(phrase in lower_text for phrase in _VERBOSE_BY_PHRASE)

        positive_matches = sum(1 for sample in positive_samples if has_match(sample))
        negative_matches = sum(1 for sample in negative_samples if has_match(sample))
        return VerbosePhraseRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            context_window_chars=self.config.context_window_chars,
        )
