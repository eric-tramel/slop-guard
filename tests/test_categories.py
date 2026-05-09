"""Tests for rule-category tagging and category_counts aggregation.

Each Rule subclass declares a ``category`` ("ai_slop" or "writing_quality").
The pipeline tags every violation it emits with the producing rule's category,
and the analyzer aggregates per-category counts into ``category_counts``.
"""

from importlib.resources import files

from slop_guard.config import DEFAULT_HYPERPARAMETERS
from slop_guard.document import AnalysisDocument
from slop_guard.engine import analyze_text
from slop_guard.rules import Pipeline
from slop_guard.rules.catalog import (
    DEFAULT_RULE_PATHS,
    WRITING_QUALITY_RULE_PATHS,
)
from slop_guard.rules.registry import resolve_rule_type


def _writing_quality_pipeline_path() -> str:
    """Return the absolute path of the packaged writing_quality.jsonl."""
    return str(files("slop_guard.rules").joinpath("assets/writing_quality.jsonl"))


def test_default_pipeline_rules_are_tagged_ai_slop() -> None:
    """All rules in the packaged default pipeline should carry category 'ai_slop'."""
    pipeline = Pipeline.from_jsonl()
    assert all(rule.category == "ai_slop" for rule in pipeline.rules)


def test_writing_quality_pipeline_rules_are_tagged_writing_quality() -> None:
    """All rules in writing_quality.jsonl should carry category 'writing_quality'."""
    pipeline = Pipeline.from_jsonl(_writing_quality_pipeline_path())
    assert all(rule.category == "writing_quality" for rule in pipeline.rules)


def test_writing_quality_pipeline_includes_every_writing_quality_rule_class() -> None:
    """writing_quality.jsonl should reference every WritingQuality rule path."""
    pipeline = Pipeline.from_jsonl(_writing_quality_pipeline_path())
    loaded_paths = {
        f"{type(rule).__module__}.{type(rule).__name__}" for rule in pipeline.rules
    }
    assert loaded_paths == set(WRITING_QUALITY_RULE_PATHS)


def test_default_paths_and_writing_quality_paths_are_disjoint() -> None:
    """The two catalogs should partition the rule space — no overlap."""
    assert set(DEFAULT_RULE_PATHS).isdisjoint(set(WRITING_QUALITY_RULE_PATHS))


def test_default_pipeline_omits_category_fields_from_payload() -> None:
    """Default ai_slop-only pipelines should not emit category/category_counts."""
    text = (
        "This is a crucial and groundbreaking paradigm that feels remarkably "
        "innovative and comprehensive overall."
    )

    result = analyze_text(text, hyperparameters=DEFAULT_HYPERPARAMETERS)

    assert result["violations"], "expected at least one violation in this text"
    assert "category_counts" not in result
    assert all("category" not in violation for violation in result["violations"])


def test_writing_quality_pipeline_violations_carry_writing_quality_category() -> None:
    """Violations emitted by the writing_quality pipeline should be tagged."""
    pipeline = Pipeline.from_jsonl(_writing_quality_pipeline_path())
    text = (
        "It is obvious that we should utilize the methodology in order to "
        "move the needle on the end result."
    )

    result = analyze_text(
        text, hyperparameters=DEFAULT_HYPERPARAMETERS, pipeline=pipeline
    )

    assert result["violations"], "expected at least one violation in this text"
    assert all(
        violation["category"] == "writing_quality" for violation in result["violations"]
    )


def test_category_counts_aggregates_violations_per_category() -> None:
    """category_counts should sum to total violation count per category."""
    pipeline = Pipeline.from_jsonl(_writing_quality_pipeline_path())
    text = (
        "It is obvious that we should utilize the methodology in order to "
        "move the needle on the end result."
    )

    result = analyze_text(
        text, hyperparameters=DEFAULT_HYPERPARAMETERS, pipeline=pipeline
    )

    total_counted = sum(result["category_counts"].values())
    assert total_counted == len(result["violations"])
    assert result["category_counts"]["writing_quality"] == len(result["violations"])


def test_category_counts_handles_mixed_pipelines() -> None:
    """Mixed pipelines should produce category_counts with both categories."""
    default_rules = list(Pipeline.from_jsonl().rules)
    writing_rules = list(Pipeline.from_jsonl(_writing_quality_pipeline_path()).rules)
    mixed_pipeline = Pipeline(default_rules + writing_rules)
    text = (
        "This crucial paradigm is groundbreaking. "
        "It is obvious that we should utilize the methodology."
    )

    result = analyze_text(
        text, hyperparameters=DEFAULT_HYPERPARAMETERS, pipeline=mixed_pipeline
    )

    assert "ai_slop" in result["category_counts"]
    assert "writing_quality" in result["category_counts"]
    assert result["category_counts"]["ai_slop"] + result["category_counts"][
        "writing_quality"
    ] == len(result["violations"])


def test_category_counts_empty_when_writing_quality_pipeline_has_no_hits() -> None:
    """Writing_quality pipeline on clean text should still emit (empty) category_counts."""
    pipeline = Pipeline.from_jsonl(_writing_quality_pipeline_path())
    text = (
        "The patch reduced p99 latency from 400 ms to 90 ms. "
        "Three retries succeeded; the fourth timed out. "
        "Cache hit rate stayed at 92% across the rollout window."
    )

    result = analyze_text(
        text, hyperparameters=DEFAULT_HYPERPARAMETERS, pipeline=pipeline
    )

    assert result["category_counts"] == {}


def test_writing_quality_rule_classes_carry_category_attribute() -> None:
    """Each writing_quality Rule class should declare category='writing_quality'."""
    for rule_path in WRITING_QUALITY_RULE_PATHS:
        rule_type = resolve_rule_type(rule_path)
        assert rule_type.category == "writing_quality", (
            f"{rule_path} missing category='writing_quality'"
        )


def test_default_rule_classes_carry_ai_slop_category() -> None:
    """Each default Rule class should declare (or inherit) category='ai_slop'."""
    for rule_path in DEFAULT_RULE_PATHS:
        rule_type = resolve_rule_type(rule_path)
        assert rule_type.category == "ai_slop", (
            f"{rule_path} category should be 'ai_slop'"
        )


def test_pipeline_tagging_does_not_mutate_rule_emitted_violations() -> None:
    """Pipeline tagging should produce new Violation instances, not mutate originals."""
    pipeline = Pipeline.from_jsonl(_writing_quality_pipeline_path())
    document = AnalysisDocument.from_text(
        "It is obvious that we should utilize the methodology."
    )

    state = pipeline.forward(document)

    assert all(
        violation.category == "writing_quality" for violation in state.violations
    )
