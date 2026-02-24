"""Tests for the modular rule framework."""


import pytest

from slop_guard.analysis import AnalysisDocument, HYPERPARAMETERS
from slop_guard.rules import Pipeline, Rule, RuleConfig, RuleLevel
from slop_guard.rules.word_level import SlopWordRule, SlopWordRuleConfig


def test_default_pipeline_covers_all_levels() -> None:
    """Default pipeline should include each configured rule level."""
    rules = Pipeline.from_jsonl().rules
    levels = {rule.level for rule in rules}
    assert levels == {
        RuleLevel.WORD,
        RuleLevel.SENTENCE,
        RuleLevel.PARAGRAPH,
        RuleLevel.PASSAGE,
    }


def test_rule_fit_validates_inputs_and_returns_self() -> None:
    """Base fit path should validate shape/types and behave scikit-style."""
    rule = SlopWordRule(
        SlopWordRuleConfig(
            penalty=HYPERPARAMETERS.slop_word_penalty,
            context_window_chars=HYPERPARAMETERS.context_window_chars,
        )
    )

    with pytest.raises(ValueError):
        rule.fit(["sample"], [1, 0])

    with pytest.raises(TypeError):
        rule.fit(["sample", 1], [1, 0])  # type: ignore[list-item]

    with pytest.raises(TypeError):
        rule.fit(["sample"], ["positive"])  # type: ignore[list-item]

    fitted = rule.fit(["sample"], [1])
    assert fitted is rule


def test_rule_to_dict_from_dict_round_trip() -> None:
    """Rules should round-trip config through base serialization helpers."""
    rule = SlopWordRule(
        SlopWordRuleConfig(
            penalty=HYPERPARAMETERS.slop_word_penalty,
            context_window_chars=HYPERPARAMETERS.context_window_chars,
        )
    )

    raw = rule.to_dict()
    assert raw == {
        "penalty": HYPERPARAMETERS.slop_word_penalty,
        "context_window_chars": HYPERPARAMETERS.context_window_chars,
    }

    rebuilt = SlopWordRule.from_dict(raw)
    assert isinstance(rebuilt, SlopWordRule)
    assert rebuilt.config == rule.config


_DEFAULT_RULES = Pipeline.from_jsonl().rules
_RULE_EXAMPLE_IDS = [
    f"{index:02d}-{rule.__class__.__name__}" for index, rule in enumerate(_DEFAULT_RULES)
]


@pytest.mark.parametrize("rule", _DEFAULT_RULES, ids=_RULE_EXAMPLE_IDS)
def test_rule_examples_match_rule_forward_behavior(rule: Rule[RuleConfig]) -> None:
    """Each rule should pass its own example violations and non-violations."""
    violation_examples = rule.example_violations()
    non_violation_examples = rule.example_non_violations()

    assert violation_examples, (
        f"{rule.__class__.__name__} must define at least one violation example"
    )
    assert non_violation_examples, (
        f"{rule.__class__.__name__} must define at least one non-violation example"
    )

    for text in violation_examples:
        result = rule.forward(AnalysisDocument.from_text(text))
        assert any(violation.rule == rule.name for violation in result.violations), (
            f"{rule.__class__.__name__} expected violation for: {text!r}"
        )

    for text in non_violation_examples:
        result = rule.forward(AnalysisDocument.from_text(text))
        assert not result.violations, (
            f"{rule.__class__.__name__} expected no violations for: {text!r}"
        )
