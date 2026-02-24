"""Rule registry and class resolution helpers."""


from typing import TypeAlias

from .base import Rule, RuleConfig
from .paragraph_level import (
    BlockquoteDensityRule,
    BoldTermBulletRunRule,
    BulletDensityRule,
    HorizontalRuleOveruseRule,
    StructuralPatternRule,
)
from .passage_level import (
    ColonDensityRule,
    EmDashDensityRule,
    PhraseReuseRule,
    RhythmRule,
)
from .sentence_level import (
    AIDisclosureRule,
    ContrastPairRule,
    PithyFragmentRule,
    PlaceholderRule,
    SetupResolutionRule,
    SlopPhraseRule,
    ToneMarkerRule,
    WeaselPhraseRule,
)
from .word_level import SlopWordRule

RuleType: TypeAlias = type[Rule[RuleConfig]]
RuleList: TypeAlias = list[Rule[RuleConfig]]

DEFAULT_RULE_TYPES: tuple[RuleType, ...] = (
    SlopWordRule,
    SlopPhraseRule,
    StructuralPatternRule,
    ToneMarkerRule,
    WeaselPhraseRule,
    AIDisclosureRule,
    PlaceholderRule,
    RhythmRule,
    EmDashDensityRule,
    ContrastPairRule,
    SetupResolutionRule,
    ColonDensityRule,
    PithyFragmentRule,
    BulletDensityRule,
    BlockquoteDensityRule,
    BoldTermBulletRunRule,
    HorizontalRuleOveruseRule,
    PhraseReuseRule,
)


def rule_type_name(rule_type: RuleType) -> str:
    """Return the canonical fully-qualified name for a rule class."""
    return f"{rule_type.__module__}.{rule_type.__name__}"


_RULE_TYPES_BY_KEY: dict[str, RuleType] = {}
for _rule_type in DEFAULT_RULE_TYPES:
    _RULE_TYPES_BY_KEY[rule_type_name(_rule_type)] = _rule_type
    _RULE_TYPES_BY_KEY[_rule_type.__name__] = _rule_type
del _rule_type


def resolve_rule_type(rule_type: str) -> RuleType:
    """Resolve a rule class from a full or short class name."""
    resolved = _RULE_TYPES_BY_KEY.get(rule_type)
    if resolved is None:
        known = ", ".join(sorted(_RULE_TYPES_BY_KEY))
        raise KeyError(f"Unknown rule_type '{rule_type}'. Known rule types: {known}")
    return resolved
