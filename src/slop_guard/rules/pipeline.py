"""Rule pipeline orchestration and JSONL serialization helpers."""


import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import fields, is_dataclass
from importlib.resources import files
from pathlib import Path
from typing import TypeAlias

from slop_guard.analysis import (
    AnalysisDocument,
    AnalysisState,
    HYPERPARAMETERS,
    compute_weighted_sum,
)

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
        self,
        samples: list[str],
        labels: list[Label] | None = None,
        *,
        calibrate_contrastive: bool = True,
    ) -> "Pipeline":
        """Fit each rule against shared samples/labels and return self.

        Args:
            samples: Text samples used to fit each rule.
            labels: Optional integer labels. If omitted, all samples are
                treated as positives.
            calibrate_contrastive: Whether to run post-fit contrastive penalty
                calibration when both positive and negative labels exist.
        """
        fit_labels = labels if labels is not None else [1] * len(samples)
        for rule in self.rules:
            rule.fit(samples, fit_labels)
        if calibrate_contrastive:
            self._calibrate_contrastive_penalties(samples, fit_labels)
        return self

    def _calibrate_contrastive_penalties(
        self,
        samples: list[str],
        labels: list[Label],
    ) -> None:
        """Calibrate penalties so fitted rules separate positives from negatives.

        The scorer always uses ``abs(penalty)``, so signs cannot reward positives.
        This pass therefore attenuates or disables rules whose fitted behavior is
        anti-correlated with labels (higher average contribution on positives).
        """
        has_positive = any(label > 0 for label in labels)
        has_negative = any(label <= 0 for label in labels)
        if not has_positive or not has_negative:
            return

        documents = [AnalysisDocument.from_text(sample) for sample in samples]
        positive_indices = [index for index, label in enumerate(labels) if label > 0]
        negative_indices = [index for index, label in enumerate(labels) if label <= 0]

        for rule in self.rules:
            penalty_fields = _penalty_field_names(rule.config)
            if not penalty_fields:
                continue

            contributions: list[float] = []
            for document in documents:
                result = rule.forward(document)
                contribution = compute_weighted_sum(
                    list(result.violations),
                    result.count_deltas,
                    HYPERPARAMETERS,
                )
                contributions.append(contribution)

            positive_mean = _mean_at_indices(contributions, positive_indices)
            negative_mean = _mean_at_indices(contributions, negative_indices)
            positive_fire_rate = _rate_nonzero_at_indices(contributions, positive_indices)
            negative_fire_rate = _rate_nonzero_at_indices(contributions, negative_indices)

            scale = 1.0
            if negative_mean <= positive_mean:
                scale = 0.0
            elif negative_fire_rate <= positive_fire_rate:
                scale = 0.5
            elif positive_fire_rate > 0.80:
                scale = 0.5

            if scale < 1.0:
                _scale_penalty_fields(rule.config, penalty_fields, scale)


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


def _penalty_field_names(config: RuleConfig) -> tuple[str, ...]:
    """Return names of dataclass int fields that encode penalty magnitudes."""
    if not is_dataclass(config):
        return ()
    names: list[str] = []
    for field in fields(config):
        value = getattr(config, field.name)
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        if (
            field.name == "penalty"
            or field.name.endswith("_penalty")
            or field.name.endswith("_penalty_step")
        ):
            names.append(field.name)
    return tuple(names)


def _scale_penalty_fields(
    config: RuleConfig, field_names: tuple[str, ...], scale: float
) -> None:
    """Scale selected config penalty fields in-place."""
    if scale < 0.0:
        raise ValueError("scale must be non-negative")
    for field_name in field_names:
        value = getattr(config, field_name)
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        if value == 0 or scale == 0.0:
            setattr(config, field_name, 0)
            continue

        scaled_magnitude = max(1, int(round(abs(value) * scale)))
        setattr(config, field_name, -scaled_magnitude if value < 0 else scaled_magnitude)


def _mean_at_indices(values: list[float], indices: list[int]) -> float:
    """Return mean for selected indices; zero when empty."""
    if not indices:
        return 0.0
    total = sum(values[index] for index in indices)
    return total / len(indices)


def _rate_nonzero_at_indices(values: list[float], indices: list[int]) -> float:
    """Return fraction of selected indices where value is nonzero."""
    if not indices:
        return 0.0
    nonzero = sum(1 for index in indices if not math.isclose(values[index], 0.0))
    return nonzero / len(indices)
