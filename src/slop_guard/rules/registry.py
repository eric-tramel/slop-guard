"""Rule registry and class resolution helpers."""

from importlib import import_module
from typing import Any, TypeAlias

from .base import Rule
from .catalog import DEFAULT_RULE_PATHS

RuleType: TypeAlias = type[Rule[Any]]
RuleList: TypeAlias = list[Rule[Any]]

_RULE_TYPES_BY_KEY: dict[str, RuleType] = {}
_RULE_PATHS_BY_KEY: dict[str, str] = {}


def rule_type_name(rule_type: RuleType) -> str:
    """Return the canonical fully-qualified name for a rule class."""
    return f"{rule_type.__module__}.{rule_type.__name__}"


def _load_rule_type(rule_path: str) -> RuleType:
    """Load one concrete rule class from a dotted import path."""
    module_name, _, class_name = rule_path.rpartition(".")
    if not module_name or not class_name:
        raise KeyError(f"Unknown rule_type '{rule_path}'")
    module = import_module(module_name)
    rule_type = getattr(module, class_name)
    if not isinstance(rule_type, type) or not issubclass(rule_type, Rule):
        raise TypeError(f"{rule_path} is not a Rule subclass")
    return rule_type


def _register_rule_type(rule_type: RuleType) -> RuleType:
    """Cache one rule class under both its long and short names."""
    _RULE_TYPES_BY_KEY[rule_type_name(rule_type)] = rule_type
    _RULE_TYPES_BY_KEY[rule_type.__name__] = rule_type
    return rule_type


for _rule_path in DEFAULT_RULE_PATHS:
    _RULE_PATHS_BY_KEY[_rule_path] = _rule_path
    _RULE_PATHS_BY_KEY[_rule_path.rpartition(".")[2]] = _rule_path


def default_rule_types() -> tuple[RuleType, ...]:
    """Return the builtin rule classes in packaged default order."""
    return tuple(resolve_rule_type(path) for path in DEFAULT_RULE_PATHS)


def resolve_rule_type(rule_type: str) -> RuleType:
    """Resolve a rule class from a full or short class name."""
    resolved = _RULE_TYPES_BY_KEY.get(rule_type)
    if resolved is None:
        rule_path = _RULE_PATHS_BY_KEY.get(rule_type)
        if rule_path is not None:
            resolved = _register_rule_type(_load_rule_type(rule_path))
    if resolved is None:
        known = ", ".join(sorted(_RULE_PATHS_BY_KEY))
        raise KeyError(f"Unknown rule_type '{rule_type}'. Known rule types: {known}")
    return resolved
