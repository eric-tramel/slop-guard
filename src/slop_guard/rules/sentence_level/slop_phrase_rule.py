"""Detect stock slop phrases and transition templates.

Objective: Catch boilerplate sentence-level phrases that announce structure,
pad prose, or sound like assistant scripting rather than direct authorship.

Example Rule Violations:
    - "It's worth noting that reliability matters."
      Uses a canned setup phrase instead of stating the claim directly.
    - "If you want, I can adapt this into a checklist."
      Uses assistant-menu phrasing that breaks authored prose voice.

Example Non-Violations:
    - "Reliability matters because retries hide partial failures."
      Direct assertion with rationale and no framing template.
    - "The next section covers deployment constraints."
      Legitimate transition written in plain style.

Severity: Medium; each hit is a strong indicator of templated writing style.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from slop_guard.analysis import AnalysisDocument, RuleResult, Violation, context_around

from slop_guard.rules.base import Rule, RuleConfig, RuleLevel

_SLOP_PHRASES_LITERAL = (
    "it's worth noting",
    "it's important to note",
    "this is where things get interesting",
    "here's the thing",
    "at the end of the day",
    "in today's fast-paced",
    "as technology continues to",
    "something shifted",
    "everything changed",
    "the answer? it's simpler than you think",
    "what makes this work is",
    "this is exactly",
    "let's break this down",
    "let's dive in",
    "in this post, we'll explore",
    "in this article, we'll",
    "let me know if",
    "would you like me to",
    "i hope this helps",
    "as mentioned earlier",
    "as i mentioned",
    "without further ado",
    "on the other hand",
    "in addition",
    "in summary",
    "in conclusion",
    "you might be wondering",
    "the obvious question is",
    "no discussion would be complete",
    "great question",
    "that's a great",
    "if you want, i can",
    "i can adapt this",
    "i can make this",
    "here are some options",
    "here are a few options",
    "would you prefer",
    "shall i",
    "if you'd like, i can",
    "i can also",
    "in other words",
    "put differently",
    "that is to say",
    "to put it simply",
    "to put it another way",
    "what this means is",
    "the takeaway is",
    "the bottom line is",
    "the key takeaway",
    "the key insight",
)

_SLOP_PHRASES_RE_LIST: tuple[re.Pattern[str], ...] = tuple(
    re.compile(re.escape(phrase), re.IGNORECASE)
    for phrase in _SLOP_PHRASES_LITERAL
)

_NOT_JUST_BUT_RE = re.compile(
    r"not (just|only) .{1,40}, but (also )?", re.IGNORECASE
)


@dataclass
class SlopPhraseRuleConfig(RuleConfig):
    """Config for phrase-level slop pattern matching."""

    penalty: int
    context_window_chars: int


class SlopPhraseRule(Rule[SlopPhraseRuleConfig]):
    """Detect stock slop phrases and the "not just X, but" pattern."""

    name = "slop_phrase"
    count_key = "slop_phrases"
    level = RuleLevel.SENTENCE

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply phrase and transition pattern checks."""
        violations: list[Violation] = []
        advice: list[str] = []
        count = 0

        for pattern in _SLOP_PHRASES_RE_LIST:
            for match in pattern.finditer(document.text):
                phrase = match.group(0).lower()
                violations.append(
                    Violation(
                        rule=self.name,
                        match=phrase,
                        context=context_around(
                            document.text,
                            match.start(),
                            match.end(),
                            width=self.config.context_window_chars,
                        ),
                        penalty=self.config.penalty,
                    )
                )
                advice.append(
                    f"Cut '{phrase}' \u2014 just state the point directly."
                )
                count += 1

        for match in _NOT_JUST_BUT_RE.finditer(document.text):
            phrase = match.group(0).strip().lower()
            violations.append(
                Violation(
                    rule=self.name,
                    match=phrase,
                    context=context_around(
                        document.text,
                        match.start(),
                        match.end(),
                        width=self.config.context_window_chars,
                    ),
                    penalty=self.config.penalty,
                )
            )
            advice.append(
                f"Cut '{phrase}' \u2014 just state the point directly."
            )
            count += 1

        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: count} if count else {},
        )
