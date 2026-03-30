"""Sentence-level rules."""

from .ai_disclosure import AIDisclosureRule, AIDisclosureRuleConfig
from .contrast_pair import ContrastPairRule, ContrastPairRuleConfig
from .pithy_fragment import PithyFragmentRule, PithyFragmentRuleConfig
from .placeholder import PlaceholderRule, PlaceholderRuleConfig
from .setup_resolution import SetupResolutionRule, SetupResolutionRuleConfig
from .slop_phrase import SlopPhraseRule, SlopPhraseRuleConfig
from .tone_marker import ToneMarkerRule, ToneMarkerRuleConfig
from .weasel_phrase import WeaselPhraseRule, WeaselPhraseRuleConfig

__all__ = [
    "AIDisclosureRule",
    "AIDisclosureRuleConfig",
    "ContrastPairRule",
    "ContrastPairRuleConfig",
    "PithyFragmentRule",
    "PithyFragmentRuleConfig",
    "PlaceholderRule",
    "PlaceholderRuleConfig",
    "SetupResolutionRule",
    "SetupResolutionRuleConfig",
    "SlopPhraseRule",
    "SlopPhraseRuleConfig",
    "ToneMarkerRule",
    "ToneMarkerRuleConfig",
    "WeaselPhraseRule",
    "WeaselPhraseRuleConfig",
]
