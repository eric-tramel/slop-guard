"""Tests for JSONL-backed rule pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from slop_guard.analysis import AnalysisDocument, RuleResult
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
