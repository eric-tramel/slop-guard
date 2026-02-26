"""Tests for JSONL-backed rule pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from slop_guard.analysis import (
    AnalysisDocument,
    HYPERPARAMETERS,
    RuleResult,
    Violation,
    compute_weighted_sum,
)
from slop_guard.rules import Pipeline, Rule, RuleConfig, run_rule_pipeline


def test_pipeline_jsonl_round_trip_preserves_rules_and_configs(
    tmp_path: Path,
) -> None:
    """Writing then reading a pipeline should preserve order and settings."""
    pipeline = Pipeline.from_jsonl()
    output_path = tmp_path / "round_trip.jsonl"
    pipeline.to_jsonl(output_path)

    rebuilt = Pipeline.from_jsonl(output_path)
    assert [type(rule) for rule in rebuilt.rules] == [
        type(rule) for rule in pipeline.rules
    ]
    assert [rule.to_dict() for rule in rebuilt.rules] == [
        rule.to_dict() for rule in pipeline.rules
    ]


def test_pipeline_forward_matches_legacy_helper() -> None:
    """Pipeline.forward should match the helper-style pipeline execution."""
    document = AnalysisDocument.from_text(
        "This is a crucial and groundbreaking paradigm for modern teams."
    )
    pipeline = Pipeline.from_jsonl()

    assert pipeline.forward(document) == run_rule_pipeline(document, pipeline.rules)


@dataclass
class _RecordingConfig(RuleConfig):
    """Minimal config used by the recording test rule."""

    fit_count: int


class _RecordingRule(Rule[_RecordingConfig]):
    """Test helper rule that records fit inputs."""

    name = "recording"
    count_key = "recording"
    fit_calls: list[tuple[list[str], list[int]]] = []

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Return an empty result for fit-focused testing."""
        _ = document
        return RuleResult()

    def example_violations(self) -> list[str]:
        """Return one example to satisfy the abstract interface."""
        return ["violation example"]

    def example_non_violations(self) -> list[str]:
        """Return one non-example to satisfy the abstract interface."""
        return ["non-violation example"]

    def _fit(self, samples: list[str], labels: list[int]) -> _RecordingConfig:
        """Record fit inputs and increment fit count."""
        self.fit_calls.append((list(samples), list(labels)))
        return _RecordingConfig(fit_count=self.config.fit_count + 1)


def test_pipeline_fit_runs_all_rules_and_supports_default_labels() -> None:
    """Pipeline.fit should fit each rule and default labels to all positives."""
    _RecordingRule.fit_calls = []

    first = _RecordingRule(_RecordingConfig(fit_count=0))
    second = _RecordingRule(_RecordingConfig(fit_count=1))
    pipeline = Pipeline([first, second])

    fitted = pipeline.fit(["alpha", "beta"])

    assert fitted is pipeline
    assert _RecordingRule.fit_calls == [
        (["alpha", "beta"], [1, 1]),
        (["alpha", "beta"], [1, 1]),
    ]
    assert first.config.fit_count == 1
    assert second.config.fit_count == 2


@dataclass
class _MarkerPenaltyConfig(RuleConfig):
    """Config for marker-triggered penalty test rules."""

    penalty: int
    marker: str


class _MarkerPenaltyRule(Rule[_MarkerPenaltyConfig]):
    """Emit one violation when a marker token is present."""

    name = "marker_penalty"
    count_key = "marker_penalty"

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Return one marker-based violation when configured marker is present."""
        if self.config.marker not in document.text:
            return RuleResult()
        return RuleResult(
            violations=[
                Violation(
                    rule=self.name,
                    match=self.config.marker,
                    context=self.config.marker,
                    penalty=self.config.penalty,
                )
            ],
            count_deltas={self.count_key: 1},
        )

    def example_violations(self) -> list[str]:
        """Return one synthetic violation example."""
        return [self.config.marker]

    def example_non_violations(self) -> list[str]:
        """Return one synthetic non-violation example."""
        return ["absent marker"]

    def _fit(
        self, samples: list[str], labels: list[int] | None
    ) -> _MarkerPenaltyConfig:
        """Keep config unchanged so calibration behavior is isolated."""
        _ = samples
        _ = labels
        return self.config


def test_pipeline_fit_calibrates_penalties_for_contrastive_labels() -> None:
    """Contrastive calibration should disable anti-correlated penalties."""
    positive_rule = _MarkerPenaltyRule(
        _MarkerPenaltyConfig(penalty=-5, marker="POS_ONLY_MARKER")
    )
    negative_rule = _MarkerPenaltyRule(
        _MarkerPenaltyConfig(penalty=-5, marker="NEG_ONLY_MARKER")
    )
    pipeline = Pipeline([positive_rule, negative_rule])

    samples = [
        "This text has POS_ONLY_MARKER",
        "This text has NEG_ONLY_MARKER",
    ]
    labels = [1, 0]
    pipeline.fit(samples, labels)

    assert positive_rule.config.penalty == 0
    assert negative_rule.config.penalty < 0

    positive_doc = AnalysisDocument.from_text(samples[0])
    negative_doc = AnalysisDocument.from_text(samples[1])
    positive_state = pipeline.forward(positive_doc)
    negative_state = pipeline.forward(negative_doc)
    positive_weighted = compute_weighted_sum(
        list(positive_state.violations), positive_state.counts, HYPERPARAMETERS
    )
    negative_weighted = compute_weighted_sum(
        list(negative_state.violations), negative_state.counts, HYPERPARAMETERS
    )
    assert positive_weighted < negative_weighted


def test_pipeline_fit_can_skip_contrastive_calibration() -> None:
    """Callers should be able to skip calibration for faster fitting."""
    positive_rule = _MarkerPenaltyRule(
        _MarkerPenaltyConfig(penalty=-5, marker="POS_ONLY_MARKER")
    )
    negative_rule = _MarkerPenaltyRule(
        _MarkerPenaltyConfig(penalty=-5, marker="NEG_ONLY_MARKER")
    )
    pipeline = Pipeline([positive_rule, negative_rule])

    samples = [
        "This text has POS_ONLY_MARKER",
        "This text has NEG_ONLY_MARKER",
    ]
    labels = [1, 0]
    pipeline.fit(samples, labels, calibrate_contrastive=False)

    assert positive_rule.config.penalty == -5
    assert negative_rule.config.penalty == -5
