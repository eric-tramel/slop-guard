"""Detect moderately long sentences with a per-document cap.

Objective: Flag any single sentence exceeding a word-count threshold, capping
how many such hits a single document can contribute. This is a lighter-touch
companion to ``ExtremeSentenceRule`` (which targets only true run-ons at a
much higher threshold).

Example Rule Violations:
    - A single sentence of 45 words chaining several clauses with commas and
      conjunctions instead of breaking into shorter statements.

Example Non-Violations:
    - "The update shipped on Tuesday."
      Short, direct sentence.
    - A passage where every sentence stays under the configured threshold.

Severity: Medium per hit, capped at ``max_hits`` so one bad section can't
saturate the score on its own.
"""

from dataclasses import dataclass, field

from slop_guard.document import AnalysisDocument
from slop_guard.models import RuleResult, Violation
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import fit_penalty_contrastive


@dataclass
class LongSentenceRuleConfig(RuleConfig):
    """Config for long-sentence detection with a per-document cap."""

    min_words: int = field(
        metadata={
            "description": (
                "Minimum sentence length (in words) that qualifies as long; "
                "any sentence with at least this many words emits a violation."
            )
        }
    )
    max_hits: int = field(
        metadata={
            "description": (
                "Maximum number of long-sentence violations recorded per "
                "document. Additional matches beyond this cap are ignored."
            )
        }
    )
    penalty: int = field(
        metadata={
            "description": ("Penalty applied per long-sentence hit, up to max_hits.")
        }
    )


class LongSentenceRule(Rule[LongSentenceRuleConfig]):
    """Flag sentences exceeding ``min_words``, capped at ``max_hits``."""

    name = "long_sentence"
    count_key = "long_sentence"
    level = RuleLevel.PASSAGE
    category = "writing_quality"

    def example_violations(self) -> list[str]:
        """Return samples that should trigger long-sentence matches."""
        return [
            " ".join(["word"] * (self.config.min_words + 5)),
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid long-sentence matches."""
        return [
            "Short sentences keep ideas separate. Each one carries one claim.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Walk sentences and emit a violation per qualifying hit, up to cap."""
        violations: list[Violation] = []
        advice: list[str] = []

        for idx, (sentence, word_count) in enumerate(
            zip(
                document.sentence_analysis_sentences,
                document.sentence_analysis_word_counts,
            )
        ):
            if word_count < self.config.min_words:
                continue
            if len(violations) >= self.config.max_hits:
                break
            preview = f'"{sentence[:80]}..."' if len(sentence) > 80 else f'"{sentence}"'
            violations.append(
                Violation(
                    rule=self.name,
                    match="long_sentence",
                    context=(
                        f"Sentence {idx + 1} has {word_count} words "
                        f"(>= {self.config.min_words}): {preview}"
                    ),
                    penalty=self.config.penalty,
                )
            )
            advice.append(
                f"Sentence {idx + 1} is {word_count} words — break it into shorter sentences."
            )

        if not violations:
            return RuleResult()

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(violations)},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> LongSentenceRuleConfig:
        """Fit penalty from long-sentence prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def has_long(sample: str) -> bool:
            doc = AnalysisDocument.from_text(sample)
            return any(
                wc >= self.config.min_words for wc in doc.sentence_analysis_word_counts
            )

        positive_matches = sum(1 for sample in positive_samples if has_long(sample))
        negative_matches = sum(1 for sample in negative_samples if has_long(sample))
        return LongSentenceRuleConfig(
            min_words=self.config.min_words,
            max_hits=self.config.max_hits,
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
        )
