"""Detect extremely long run-on sentences.

Objective: Flag any single sentence exceeding a word-count threshold.  AI can
generate massive run-on sentences with nested subordinate clauses that
circumvent per-sentence rhythm analysis.

Example Rule Violations:
    - A single sentence of 90 words chaining subordinate clause after subordinate
      clause with commas and conjunctions.
      The sheer length signals generated rather than drafted prose.

Example Non-Violations:
    - "The update shipped on Tuesday." - short, direct sentence.
    - A passage where every sentence stays under 40 words.

Severity: Medium; each hit adds structural evidence of generated text.
"""


from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation

from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import fit_penalty_contrastive


@dataclass
class ExtremeSentenceRuleConfig(RuleConfig):
    """Config for extreme sentence length detection."""

    min_words: int
    penalty: int


class ExtremeSentenceRule(Rule[ExtremeSentenceRuleConfig]):
    """Flag any sentence that exceeds the configured word-count threshold."""

    name = "extreme_sentence"
    count_key = "extreme_sentence"
    level = RuleLevel.PASSAGE

    def example_violations(self) -> list[str]:
        """Return samples that should trigger extreme-sentence matches."""
        return [
            " ".join(["word"] * 85),
        ]

    def example_non_violations(self) -> list[str]:
        """Return samples that should avoid extreme-sentence matches."""
        return [
            "This is a normal sentence. And so is this one.",
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Scan all sentences and flag any that exceed min_words."""
        violations: list[Violation] = []
        advice: list[str] = []
        count = 0

        for idx, (sentence, wc) in enumerate(
            zip(document.sentences, document.sentence_word_counts)
        ):
            if wc >= self.config.min_words:
                preview = f'"{sentence[:80]}..."' if len(sentence) > 80 else f'"{sentence}"'
                violations.append(
                    Violation(
                        rule=self.name,
                        match="run_on_sentence",
                        context=(
                            f"Sentence {idx + 1} has {wc} words "
                            f"(>= {self.config.min_words}): {preview}"
                        ),
                        penalty=self.config.penalty,
                    )
                )
                advice.append(
                    f"Sentence {idx + 1} is {wc} words - break it into "
                    "shorter sentences."
                )
                count += 1

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: count} if count else {},
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> ExtremeSentenceRuleConfig:
        """Fit penalty from extreme-sentence prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def has_extreme(sample: str) -> bool:
            doc = AnalysisDocument.from_text(sample)
            return any(wc >= self.config.min_words for wc in doc.sentence_word_counts)

        positive_matches = sum(1 for s in positive_samples if has_extreme(s))
        negative_matches = sum(1 for s in negative_samples if has_extreme(s))
        return ExtremeSentenceRuleConfig(
            min_words=self.config.min_words,
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=positive_matches,
                positive_total=len(positive_samples),
                negative_matches=negative_matches,
                negative_total=len(negative_samples),
            ),
        )
