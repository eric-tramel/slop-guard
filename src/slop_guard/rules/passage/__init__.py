"""Passage-level rules."""

from .closing_aphorism import ClosingAphorismRule, ClosingAphorismRuleConfig
from .colon_density import ColonDensityRule, ColonDensityRuleConfig
from .copula_chain import CopulaChainRule, CopulaChainRuleConfig
from .em_dash_density import EmDashDensityRule, EmDashDensityRuleConfig
from .extreme_sentence import ExtremeSentenceRule, ExtremeSentenceRuleConfig
from .paragraph_rhythm import (
    ParagraphBalanceRule,
    ParagraphBalanceRuleConfig,
    ParagraphCVRule,
    ParagraphCVRuleConfig,
)
from .phrase_reuse import PhraseReuseRule, PhraseReuseRuleConfig
from .rhythm import RhythmRule, RhythmRuleConfig

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
