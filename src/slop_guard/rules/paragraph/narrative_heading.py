"""Detect narrative-poetic Markdown headings.

Objective: Flag headings of the form "## The {Abstract Noun} of ..." which
are a strong AI-style structural tell ("The Journey of ...", "The Art of ...",
"The Power of ..."). These almost always replace a concrete, scannable
section title.

Example Rule Violations:
    - "## The Journey of Refactoring"
    - "## The Art of Caching"
    - "## The Power of Idempotence"

Example Non-Violations:
    - "## Caching strategy"
    - "## How retries work"
    - "## Refactor plan"

Severity: High per hit; the pattern is rare in authored prose.
"""

import re
from dataclasses import dataclass, field

from slop_guard.document import AnalysisDocument, context_around
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import fit_penalty_contrastive

_NARRATIVE_NOUN_PATTERN = (
    "Journey|Art|Power|Beauty|Magic|Essence|Heart|Soul|Spirit|Pursuit|"
    "Quest|Path|Rise|Dawn|Era|Age|Future|Promise|Wonder"
)
_NARRATIVE_HEADING_RE = re.compile(
    rf"^\s*#{{1,6}}\s+The\s+(?:{_NARRATIVE_NOUN_PATTERN})\s+of\b.*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class NarrativeHeadingRuleConfig(RuleConfig):
    """Config for narrative-poetic Markdown heading detection."""

    penalty: int = field(
        metadata={
            "description": ("Penalty applied per matched narrative-poetic heading.")
        }
    )
    context_window_chars: int = field(
        metadata={
            "description": (
                "Half-width (in characters) of the surrounding-text window "
                "captured as context for each narrative-heading violation."
            )
        }
    )


class NarrativeHeadingRule(Rule[NarrativeHeadingRuleConfig]):
    """Flag headings of the form '## The {abstract noun} of ...'."""

    name = "narrative_heading"
    count_key = "narrative_heading"
    level = RuleLevel.PARAGRAPH
    category = "writing_quality"

    def example_violations(self) -> list[str]:
        """Return samples that should trigger narrative-heading matches."""
        return [
            "## The Journey of Refactoring",
            "### The Art of Caching",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid narrative-heading matches."""
        return [
            "## Caching strategy",
            "## Refactor plan",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Match narrative-poetic Markdown headings and emit one violation each."""
        violations: list[Violation] = []
        for match in _NARRATIVE_HEADING_RE.finditer(document.text):
            heading = match.group(0).strip()
            violations.append(
                Violation(
                    rule=self.name,
                    match="narrative_heading",
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
            _ = heading

        if not violations:
            return RuleResult()

        return RuleResult(
            violations=violations,
            advice=[
                "Replace narrative-poetic headings ('The {Noun} of ...') with concrete, scannable section titles."
            ],
            count_deltas={self.count_key: len(violations)},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> NarrativeHeadingRuleConfig:
        """Fit penalty from narrative-heading prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        positive_matches = sum(
            1
            for sample in positive_samples
            if _NARRATIVE_HEADING_RE.search(sample) is not None
        )
        negative_matches = sum(
            1
            for sample in negative_samples
            if _NARRATIVE_HEADING_RE.search(sample) is not None
        )
        return NarrativeHeadingRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            context_window_chars=self.config.context_window_chars,
        )
