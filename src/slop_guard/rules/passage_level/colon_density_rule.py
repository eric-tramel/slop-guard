"""Passage-level rule detecting elaboration-colon overuse."""

from __future__ import annotations

import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, word_count

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel
from slop_guard.rules.helpers import strip_code_blocks

_ELABORATION_COLON_RE = re.compile(r": [a-z]")
_MD_HEADER_LINE_RE = re.compile(r"^\s*#", re.MULTILINE)
_JSON_COLON_RE = re.compile(r': ["{\[\d]|: true|: false|: null')


@dataclass
class ColonDensityRuleConfig(RuleConfig):
    """Config for elaboration-colon density checks."""

    words_basis: float
    density_threshold: float
    penalty: int


class ColonDensityRule(Rule[ColonDensityRuleConfig]):
    """Detect dense elaboration colons outside code and metadata contexts."""

    name = "colon_density"
    count_key = "colon_density"
    level = RuleLevel.PASSAGE

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Compute elaboration-colon density for prose lines."""
        stripped_text = strip_code_blocks(document.text)
        colon_count = 0

        for line in stripped_text.split("\n"):
            if _MD_HEADER_LINE_RE.match(line):
                continue

            for match in _ELABORATION_COLON_RE.finditer(line):
                colon_pos = match.start()
                before = line[: colon_pos + 1]
                if before.endswith("http:") or before.endswith("https:"):
                    continue
                snippet = line[colon_pos : colon_pos + 10]
                if _JSON_COLON_RE.match(snippet):
                    continue
                colon_count += 1

        stripped_word_count = word_count(stripped_text)
        if stripped_word_count <= 0:
            return RuleResult()

        ratio_per_basis = (colon_count / stripped_word_count) * self.config.words_basis
        if ratio_per_basis <= self.config.density_threshold:
            return RuleResult()

        return RuleResult(
            violations=[
                Violation(
                    rule=self.name,
                    match="colon_density",
                    context=(
                        f"{colon_count} elaboration colons in {stripped_word_count} words "
                        f"({ratio_per_basis:.1f} per 150 words)"
                    ),
                    penalty=self.config.penalty,
                )
            ],
            advice=[
                f"Too many elaboration colons ({colon_count} in {stripped_word_count} words) "
                "\u2014 use periods or restructure sentences."
            ],
            count_deltas={self.count_key: 1},
        )
