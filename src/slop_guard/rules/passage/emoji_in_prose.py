"""Detect emoji embedded in prose.

Objective: Flag pictograph characters that appear in body text, where they
typically signal informal AI-generated content rather than authored writing.
Emoji inside fenced code blocks are ignored.

Example Rule Violations:
    - "We shipped it 🚀 and the team is thrilled 🎉."
      Decorative emoji punctuation in plain prose.

Example Non-Violations:
    - "We shipped it and the team is satisfied with the result."
      No emoji in prose.

Severity: Medium per hit; emoji in prose nearly always replace a more
specific written claim.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from slop_guard.document import AnalysisDocument, context_around
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import fit_penalty_contrastive

_EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001f5ff"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f77f"
    "\U0001f780-\U0001f7ff"
    "\U0001f800-\U0001f8ff"
    "\U0001f900-\U0001f9ff"
    "\U0001fa00-\U0001fa6f"
    "\U0001fa70-\U0001faff"
    "\U00002600-\U000026ff"
    "\U00002700-\U000027bf"
    "]"
)


@dataclass
class EmojiInProseRuleConfig(RuleConfig):
    """Config for emoji-in-prose detection."""

    penalty: int = field(
        metadata={"description": ("Penalty applied per emoji match in non-code prose.")}
    )
    context_window_chars: int = field(
        metadata={
            "description": (
                "Half-width (in characters) of the surrounding-text window "
                "captured as context for each emoji violation."
            )
        }
    )


class EmojiInProseRule(Rule[EmojiInProseRuleConfig]):
    """Flag emoji characters appearing in body prose."""

    name = "emoji_in_prose"
    count_key = "emoji_in_prose"
    level = RuleLevel.PASSAGE
    category = "writing_quality"

    def example_violations(self) -> list[str]:
        """Return samples that should trigger emoji matches."""
        return [
            "We shipped it 🚀 and the team is thrilled 🎉.",
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid emoji matches."""
        return [
            "We shipped it and the team is satisfied with the result.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Find emoji characters outside fenced code and emit one hit each."""
        masked_text = document.text_with_markdown_code_masked
        violations: list[Violation] = []
        per_emoji: Counter[str] = Counter()
        for match in _EMOJI_RE.finditer(masked_text):
            char = match.group(0)
            violations.append(
                Violation(
                    rule=self.name,
                    match=char,
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
            per_emoji[char] += 1

        if not violations:
            return RuleResult()

        return RuleResult(
            violations=violations,
            advice=[
                "Remove emoji from prose — replace decorative pictographs with the words they stand in for."
            ],
            count_deltas={self.count_key: len(violations)},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> EmojiInProseRuleConfig:
        """Fit penalty from emoji prevalence in prose."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def has_match(sample: str) -> bool:
            return (
                _EMOJI_RE.search(
                    AnalysisDocument.from_text(sample).text_with_markdown_code_masked
                )
                is not None
            )

        positive_matches = sum(1 for sample in positive_samples if has_match(sample))
        negative_matches = sum(1 for sample in negative_samples if has_match(sample))
        return EmojiInProseRuleConfig(
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
            context_window_chars=self.config.context_window_chars,
        )
