"""Detect foreign and Latin phrases with plain-English equivalents.

Objective: Flag Latin/French borrowings where a plain English phrase is at
least as clear (Orwell's rule 5: never use a foreign phrase, scientific word,
or jargon word if you can think of an everyday English equivalent).

Example Rule Violations:
    - "Per se, the migration was successful."
      Uses "per se" where "by itself" reads more directly.
    - "We need an ad hoc fix vis-a-vis the regression."
      Stacks two unnecessary borrowings.

Example Non-Violations:
    - "By itself, the migration was successful."
      Plain English equivalent.
    - "We need an improvised fix for the regression."
      Direct phrasing.

Severity: Low per hit; the penalty is light because some technical writing
legitimately uses these terms.
"""

import re
from dataclasses import dataclass, field

from slop_guard.document import AnalysisDocument, context_around
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import fit_penalty_contrastive

_FOREIGN_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("per se", "by itself"),
    ("vis-a-vis", "compared to"),
    ("vis-à-vis", "compared to"),
    ("ad hoc", "improvised"),
    ("de facto", "in practice"),
    ("status quo", "current state"),
    ("ipso facto", "by that fact"),
    ("inter alia", "among others"),
    ("ergo", "so"),
    ("a priori", "from first principles"),
)
_FOREIGN_BY_PHRASE: dict[str, str] = {
    phrase.lower(): replacement for phrase, replacement in _FOREIGN_REPLACEMENTS
}
_FOREIGN_RE_LIST: tuple[re.Pattern[str], ...] = tuple(
    re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
    for phrase, _ in _FOREIGN_REPLACEMENTS
)


@dataclass
class ForeignPhraseRuleConfig(RuleConfig):
    """Config for foreign/Latin phrase matching with replacements."""

    penalty: int = field(
        metadata={
            "description": ("Penalty applied per matched foreign or Latin phrase.")
        }
    )
    context_window_chars: int = field(
        metadata={
            "description": (
                "Half-width (in characters) of the surrounding-text window "
                "captured as context for each foreign-phrase violation."
            )
        }
    )


class ForeignPhraseRule(Rule[ForeignPhraseRuleConfig]):
    """Flag Latin/French borrowings and recommend the plain-English form."""

    name = "foreign_phrase"
    count_key = "foreign_phrases"
    level = RuleLevel.SENTENCE
    category = "writing_quality"

    def example_violations(self) -> list[str]:
        """Return samples that should trigger foreign-phrase matches."""
        return [
            "Per se, the migration was successful.",
            "We need an ad hoc fix.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid foreign-phrase matches."""
        return [
            "By itself, the migration was successful.",
            "We need an improvised fix.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Match each foreign phrase and emit a replacement-aware violation."""
        violations: list[Violation] = []
        seen: set[str] = set()
        advice_order: list[str] = []
        for pattern in _FOREIGN_RE_LIST:
            for match in pattern.finditer(document.text):
                phrase = match.group(0).lower()
                replacement = _FOREIGN_BY_PHRASE.get(phrase)
                if replacement is None:
                    continue
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
            f"Replace '{phrase}' with '{_FOREIGN_BY_PHRASE[phrase]}'."
            for phrase in advice_order
        ]
        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> ForeignPhraseRuleConfig:
        """Fit penalty from foreign-phrase prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def has_match(sample: str) -> bool:
            lower_text = sample.lower()
            return any(phrase in lower_text for phrase in _FOREIGN_BY_PHRASE)

        positive_matches = sum(1 for sample in positive_samples if has_match(sample))
        negative_matches = sum(1 for sample in negative_samples if has_match(sample))
        return ForeignPhraseRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            context_window_chars=self.config.context_window_chars,
        )
