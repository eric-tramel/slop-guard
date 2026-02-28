"""Passage-level rules."""

from .closing_aphorism_rule import ClosingAphorismRule, ClosingAphorismRuleConfig
from .colon_density_rule import ColonDensityRule, ColonDensityRuleConfig
from .copula_chain_rule import CopulaChainRule, CopulaChainRuleConfig
from .em_dash_density_rule import EmDashDensityRule, EmDashDensityRuleConfig
from .extreme_sentence_rule import ExtremeSentenceRule, ExtremeSentenceRuleConfig
from .paragraph_rhythm_rule import (
    ParagraphBalanceRule,
    ParagraphBalanceRuleConfig,
    ParagraphCVRule,
    ParagraphCVRuleConfig,
)
from .phrase_reuse_rule import PhraseReuseRule, PhraseReuseRuleConfig
from .rhythm_rule import RhythmRule, RhythmRuleConfig

__all__ = [
    "ClosingAphorismRule",
    "ClosingAphorismRuleConfig",
    "ColonDensityRule",
    "ColonDensityRuleConfig",
    "CopulaChainRule",
    "CopulaChainRuleConfig",
    "EmDashDensityRule",
    "EmDashDensityRuleConfig",
    "ExtremeSentenceRule",
    "ExtremeSentenceRuleConfig",
    "ParagraphBalanceRule",
    "ParagraphBalanceRuleConfig",
    "ParagraphCVRule",
    "ParagraphCVRuleConfig",
    "PhraseReuseRule",
    "PhraseReuseRuleConfig",
    "RhythmRule",
    "RhythmRuleConfig",
]
