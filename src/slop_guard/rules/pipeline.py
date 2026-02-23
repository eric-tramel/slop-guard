"""Rule execution pipeline for analysis forward passes."""

from __future__ import annotations

from typing import TypeAlias

from slop_guard.analysis import AnalysisDocument, AnalysisState

from .base import Rule, RuleConfig

RuleList: TypeAlias = list[Rule[RuleConfig]]


def run_rule_pipeline(
    document: AnalysisDocument,
    rules: list[Rule[RuleConfig]],
) -> AnalysisState:
    """Apply an ordered list of instantiated rules and merge outputs."""
    state = AnalysisState.initial()
    for rule in rules:
        state = state.merge(rule.forward(document))
    return state
