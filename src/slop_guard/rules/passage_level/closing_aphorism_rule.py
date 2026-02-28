"""Detect moralizing or generalizing closing sentences.

Objective: Flag the final sentence of a passage when it matches patterns
associated with AI-style wrap-ups: abstract generalizations, collective "we"
moral conclusions, and "it all comes down to" framings.  LLMs reliably end
passages with a tidy generalization restating the thesis in abstract terms.
Human writers more often end on a specific detail, a fragment, or just stop.

Example Rule Violations:
    - "Ultimately, it is our choices that define the system we build."
      Abstract generalization that wraps up abstractly with "ultimately".
    - "That's the real challenge in any distributed system."
      "That's the X" closing flourish.

Example Non-Violations:
    - "The build finished in 4.2 seconds."
      Specific and concrete - no moral framing.
    - "We shipped it on Friday."
      Concrete action, not an abstraction.

Severity: Low; fires at most once per passage on the closing sentence only.
"""


import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import fit_penalty_contrastive


_CLOSING_APHORISM_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "Sometimes the X isn't Y - it's Z"
    re.compile(r"^sometimes\b", re.IGNORECASE),
    # "isn't...it's" / "not...it's" setup-resolution in a single sentence
    re.compile(r"\bisn't\b.{1,40}\bit's\b", re.IGNORECASE),
    re.compile(r"\bnot\b.{1,30}\bit's\b.{1,40}$", re.IGNORECASE),
    # "The real/true/biggest X is Y"
    re.compile(
        r"^the (real|true|actual|biggest|greatest|most important)\b", re.IGNORECASE
    ),
    # "In the end" / "Ultimately"
    re.compile(
        r"^(in the end|ultimately|at the end of the day)\b", re.IGNORECASE
    ),
    # "we bring/carry" - collective moral
    re.compile(r"\bwe (bring|carry|create|make|build|choose)\b", re.IGNORECASE),
    # "That's the X" as a wrap-up
    re.compile(r"^that's (the |what |where |why |how )", re.IGNORECASE),
    # "It comes down to"
    re.compile(r"^it (all )?(comes|boils) down to\b", re.IGNORECASE),
)

_MIN_PATTERN_MATCHES = 2


@dataclass
class ClosingAphorismRuleConfig(RuleConfig):
    """Config for closing aphorism detection."""

    min_sentences: int
    penalty: int


class ClosingAphorismRule(Rule[ClosingAphorismRuleConfig]):
    """Flag a moralizing or generalizing final sentence."""

    name = "closing_aphorism"
    count_key = "closing_aphorism"
    level = RuleLevel.PASSAGE

    def example_violations(self) -> list[str]:
        """Return samples that should trigger closing-aphorism matches."""
        return [
            (
                "We explored several design patterns here. "
                "Each has trade-offs worth understanding. "
                "The codebase grows more complex over time. "
                "Ultimately, it is our choices that define the system we build."
            ),
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid closing-aphorism matches."""
        return [
            (
                "We explored several design patterns. "
                "Each has trade-offs. "
                "The build took 4 seconds."
            ),
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Check the final sentence for aphorism patterns."""
        if len(document.sentences) < self.config.min_sentences:
            return RuleResult()

        last = document.sentences[-1]
        matches = sum(1 for pat in _CLOSING_APHORISM_PATTERNS if pat.search(last))
        if matches < _MIN_PATTERN_MATCHES:
            return RuleResult()

        preview = f'"{last[:80]}..."' if len(last) > 80 else f'"{last}"'
        return RuleResult(
            violations=[
                Violation(
                    rule=self.name,
                    match="closing_aphorism",
                    context=(
                        f"Closing sentence matches {matches} generalizing "
                        f"patterns: {preview}"
                    ),
                    penalty=self.config.penalty,
                )
            ],
            advice=[
                "Your closing sentence is a tidy generalization - a strong AI "
                "tell. End on a specific detail, a fragment, or just stop."
            ],
            count_deltas={self.count_key: 1},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> ClosingAphorismRuleConfig:
        """Fit penalty from closing-aphorism prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def has_aphorism(sample: str) -> bool:
            doc = AnalysisDocument.from_text(sample)
            if len(doc.sentences) < self.config.min_sentences:
                return False
            last = doc.sentences[-1]
            return (
                sum(1 for pat in _CLOSING_APHORISM_PATTERNS if pat.search(last))
                >= _MIN_PATTERN_MATCHES
            )

        positive_matches = sum(1 for s in positive_samples if has_aphorism(s))
        negative_matches = sum(1 for s in negative_samples if has_aphorism(s))
        return ClosingAphorismRuleConfig(
            min_sentences=self.config.min_sentences,
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
        )
