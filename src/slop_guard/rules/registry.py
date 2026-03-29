"""Rule registry and class resolution helpers."""

from typing import Any, TypeAlias

from .base import Rule
from .paragraph_level import (
    BlockquoteDensityRule,
    BoldTermBulletRunRule,
    BulletDensityRule,
    HorizontalRuleOveruseRule,
    StructuralPatternRule,
)
from .passage_level import (
    ClosingAphorismRule,
    ColonDensityRule,
    CopulaChainRule,
    EmDashDensityRule,
    ExtremeSentenceRule,
    ParagraphBalanceRule,
    ParagraphCVRule,
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

RuleType: TypeAlias = type[Rule[Any]]
RuleList: TypeAlias = list[Rule[Any]]

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
    CopulaChainRule,
    ExtremeSentenceRule,
    ClosingAphorismRule,
    ParagraphBalanceRule,
    ParagraphCVRule,
)


def rule_type_name(rule_type: RuleType) -> str:
    """Return the canonical fully-qualified name for a rule class."""
    return f"{rule_type.__module__}.{rule_type.__name__}"


def _build_rule_types_by_key() -> dict[str, RuleType]:
    """Build lookup keys for resolving packaged rule classes."""
    keys_by_rule_type: dict[str, RuleType] = {}
    for rule_type in DEFAULT_RULE_TYPES:
        keys_by_rule_type[rule_type_name(rule_type)] = rule_type
        keys_by_rule_type[rule_type.__name__] = rule_type
    return keys_by_rule_type


_RULE_TYPES_BY_KEY = _build_rule_types_by_key()


def resolve_rule_type(rule_type: str) -> RuleType:
    """Resolve a rule class from a full or short class name."""
    resolved = _RULE_TYPES_BY_KEY.get(rule_type)
    if resolved is None:
        known = ", ".join(sorted(_RULE_TYPES_BY_KEY))
        raise KeyError(f"Unknown rule_type '{rule_type}'. Known rule types: {known}")
    return resolved
