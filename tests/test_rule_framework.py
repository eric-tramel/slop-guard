"""Tests for the modular rule framework."""


import pytest

from slop_guard.analysis import HYPERPARAMETERS
from slop_guard.rules import RuleLevel, build_default_rules
from slop_guard.rules.word_level import SlopWordRule, SlopWordRuleConfig


def test_build_default_rules_covers_all_levels() -> None:
    """Default rule registry should include each configured rule level."""
    rules = build_default_rules(HYPERPARAMETERS)
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
