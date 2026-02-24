"""Rule pipeline orchestration and JSONL serialization helpers."""


import json
from collections.abc import Iterable, Mapping
from importlib.resources import files
from pathlib import Path
from typing import TypeAlias

from slop_guard.analysis import AnalysisDocument, AnalysisState

from .base import Label, Rule, RuleConfig
from .registry import resolve_rule_type, rule_type_name

RuleList: TypeAlias = list[Rule[RuleConfig]]

_RULE_TYPE_FIELD = "rule_type"
_CONFIG_FIELD = "config"


class Pipeline:
    """Ordered rule pipeline with JSONL load/save and fit orchestration."""

    def __init__(self, rules: list[Rule[RuleConfig]]) -> None:
        """Initialize a pipeline from an ordered list of instantiated rules."""
        self.rules = list(rules)

    @classmethod
    def from_jsonl(cls, path: str | Path | None = None) -> "Pipeline":
        """Build a pipeline from a JSONL rule-settings file.

        Args:
            path: JSONL path. If omitted, loads packaged defaults.
        """
        raw_lines = _read_jsonl_lines(path)
        rules = _parse_rules_from_jsonl(raw_lines)
        if not rules:
            source = "<package default>" if path is None else str(path)
            raise ValueError(f"JSONL rule configuration is empty: {source}")
        return cls(rules)

    def to_jsonl(self, path: str | Path) -> None:
        """Write this pipeline's rule settings to a JSONL file."""
        output_path = Path(path)
        with output_path.open("w", encoding="utf-8") as handle:
            for rule in self.rules:
                payload = {
                    _RULE_TYPE_FIELD: rule_type_name(type(rule)),
                    _CONFIG_FIELD: rule.to_dict(),
                }
                handle.write(json.dumps(payload, sort_keys=True))
                handle.write("\n")

    def forward(self, document: AnalysisDocument) -> AnalysisState:
        """Apply all rules in order and merge their outputs."""
        state = AnalysisState.initial()
        for rule in self.rules:
            state = state.merge(rule.forward(document))
        return state

    def fit(
        self, samples: list[str], labels: list[Label] | None = None
    ) -> "Pipeline":
        """Fit each rule against shared samples/labels and return self.

        Args:
            samples: Text samples used to fit each rule.
            labels: Optional integer labels. If omitted, all samples are
                treated as positives.
        """
        fit_labels = labels if labels is not None else [1] * len(samples)
        for rule in self.rules:
            rule.fit(samples, fit_labels)
        return self


def build_default_rules() -> RuleList:
    """Return default configured rules from packaged JSONL settings."""
    return list(Pipeline.from_jsonl().rules)


def run_rule_pipeline(
    document: AnalysisDocument,
    rules: list[Rule[RuleConfig]],
) -> AnalysisState:
    """Apply an ordered list of instantiated rules and merge outputs."""
    return Pipeline(rules).forward(document)


def _read_jsonl_lines(path: str | Path | None) -> list[str]:
    """Read raw JSONL lines from a path or packaged defaults."""
    if path is None:
        raw_text = (
            files("slop_guard.rules")
            .joinpath("assets/default.jsonl")
            .read_text(encoding="utf-8")
        )
        return raw_text.splitlines()
    return Path(path).read_text(encoding="utf-8").splitlines()


def _parse_rules_from_jsonl(lines: Iterable[str]) -> RuleList:
    """Parse and instantiate rules from JSONL lines."""
    rules: RuleList = []
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue

        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {line_number}: {exc.msg}") from exc

        if not isinstance(payload, dict):
            raise TypeError(f"Line {line_number} must be a JSON object")

        rule_type_raw = payload.get(_RULE_TYPE_FIELD)
        if not isinstance(rule_type_raw, str):
            raise TypeError(
                f"Line {line_number} must contain string '{_RULE_TYPE_FIELD}'"
            )

        config_raw = payload.get(_CONFIG_FIELD)
        if not isinstance(config_raw, Mapping):
            raise TypeError(f"Line {line_number} must contain object '{_CONFIG_FIELD}'")

        rule_type = resolve_rule_type(rule_type_raw)
        rules.append(rule_type.from_dict(config_raw))

    return rules
