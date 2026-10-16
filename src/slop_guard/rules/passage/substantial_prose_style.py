"""Check substantial prose for concrete style-guide violations.

Objective: Wait until prose reaches a configurable word count, then check the
    parts of the style guide that a deterministic linter can identify. The rule
    examines vocabulary, announced structure, number-led slogans, decorative
    characters, question-word headings, restricted relative clauses, repeated
    conjunctions, and abstractions presented as agents. Markdown code remains
    available for quoted examples because the checker masks it before matching.

Example Rule Violations:
    - "Straight answer: the workflow knows which record belongs here."
      Announces the answer and assigns human understanding to a workflow.
    - "Three interfaces, one underlying structure."
      Uses a number-led slogan instead of describing the operation.

Example Non-Violations:
    - "The operator compares each row with its source record."
      Names the actor, operation, and data directly.
    - "The reviewer records the corrected total beside the affected row."
      Describes the current process without editorial framing.

Coverage: The rule reports observable patterns, then returns a structured
    semantic-review requirement. A writing agent judges context and voice. The
    agent also reviews natural syntax and rewrite quality before claiming that
    the passage follows the complete guide.

Severity: Medium per finding. The rule applies only to substantial prose, but
    repeated findings lower the score quickly after that threshold.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from slop_guard.document import AnalysisDocument, context_around
from slop_guard.models import (
    ReviewCriterion,
    ReviewRequirement,
    RuleResult,
    Violation,
)
from slop_guard.rules.base import Label, Rule, RuleConfig, RuleLevel
from slop_guard.rules.fitting import fit_penalty_contrastive

_PROHIBITED_TERMS: tuple[str, ...] = (
    "artifact",
    "fair",
    "footgun",
    "genuine",
    "golden",
    "honest",
    "hydration",
    "inflight",
    "plumbing",
    "preflight",
    "provenance",
    "pushback",
    "runbook",
    "today",
    "tomorrow",
)
_PROHIBITED_TERM_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in _PROHIBITED_TERMS) + r")\b",
    re.IGNORECASE,
)

_SIGNPOST_PHRASES: tuple[str, ...] = (
    "and this is the part that actually matters",
    "that last point matters here",
    "the real question is",
    "what you actually care about is",
    "two things determine what the landscape looks like",
    "the distinction worth keeping straight",
    "two things this buys over a raw call",
    "the fundamental insight",
    "fundamental insight",
    "the deepest lesson",
    "deepest lesson",
    "straight answer:",
    "short version:",
    "here's the thing",
    "here is the thing",
)
_SIGNPOST_RE = re.compile(
    "|".join(
        re.escape(phrase)
        for phrase in sorted(
            _SIGNPOST_PHRASES,
            key=lambda phrase: len(phrase),
            reverse=True,
        )
    ),
    re.IGNORECASE,
)
_OPENING_SIGNPOST_RE = re.compile(
    r"(?im)(?:^\s*|(?<=[.!?])\s+)(?P<claim>to summarize\b)"
)

_QUESTION_HEADING_RE = re.compile(
    r"(?m)^\s{0,3}#{1,6}\s+(?:what|why|how|when|where|who|which)\b[^\n]*",
    re.IGNORECASE,
)
_COUNT_WORD = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
_COUNTING_CLAIM_RE = re.compile(
    rf"(?im)(?:^\s*|(?<=[.!?])\s+)(?P<claim>{_COUNT_WORD}\s+"
    rf"[^\n.!?]{{1,80}}?(?::[^\n.!?]*|,\s+(?:and\s+)?{_COUNT_WORD}\b"
    rf"[^\n.!?]*)[.!?]?)"
)
_ABSTRACT_AGENT_RE = re.compile(
    r"\b(?:the|this|that|a|an)\s+"
    r"(?:architecture|argument|body|check|code|column|contract|database|design|"
    r"deployment|feature|implementation|interface|lock|method|model|parser|patch|"
    r"pipeline|process|prose|release|rule|schema|server|story|system|text|tool|"
    r"trigger|workflow|change)\s+"
    r"(?:buys?|earns?|hugs?|knows?|lands?|mints?|names?|owns?|pins?|reaches?|"
    r"sees?|shapes?|ships?|sits?|smokes?|speaks?|surfaces?|touches?|triages?|"
    r"wants?|welds?|wires?)\b[^.!?\n]*",
    re.IGNORECASE,
)
_PROCESS_SUBJECT_RE = re.compile(
    r"(?:^|(?<=[.!?])\s+)"
    r"(?P<claim>[A-Z][a-z]+ing\s+"
    r"(?:causes?|creates?|generates?|makes?|manufactures?|produces?|transfers?)"
    r"\b[^.!?\n]*)",
    re.MULTILINE,
)
_ONE_AS_ARTICLE_RE = re.compile(
    r"\b(?:accepts?|creates?|fetches?|opens?|reads?|receives?|returns?|takes?|"
    r"uses?|writes?)\s+one\s+(?:provided\s+)?[A-Za-z][\w'-]*\b",
    re.IGNORECASE,
)
_RESTRICTED_RELATIVE_RE = re.compile(
    r"\b(?:the|a|an|this|these|those|each|every)\s+"
    r"(?:[A-Za-z][\w'-]*\s+)?(?:that|which|who)\s+[A-Za-z][\w'-]*\b",
    re.IGNORECASE,
)
_NEGATIVE_ADDENDUM_RE = re.compile(
    r",\s+(?P<claim>and\s+(?:can|could|did|do|does|had|has|have|is|are|was|"
    r"were|will|would|should)\s+not\b[^.!?\n]*)",
    re.IGNORECASE,
)
_IDENTITY_FORMULA_RE = re.compile(
    r"\bthe\s+[A-Za-z][\w'-]*(?:\s+[A-Za-z][\w'-]*){0,2}\s+is\s+the\s+"
    r"[A-Za-z][\w'-]*(?:\s+[A-Za-z][\w'-]*){0,2}\b",
    re.IGNORECASE,
)
_PAREN_COMMA_CHAIN_RE = re.compile(r"\([^()\n]*,[^()\n]*,[^()\n]*,[^()\n]*\)")
_SENTENCE_SPAN_RE = re.compile(r"[^.!?\n]+")
_AND_RE = re.compile(r"\band\b", re.IGNORECASE)
_QUESTION_WORD_RE = re.compile(
    r"(?:what|who|which)\b",
    re.IGNORECASE,
)
_HTML_CODE_RE = re.compile(r"<code\b[^>]*>.*?</code>", re.IGNORECASE | re.DOTALL)
_DECORATIVE_CODEPOINT_RANGES: tuple[tuple[int, int], ...] = (
    (0x2600, 0x27BF),
    (0x1F000, 0x1FAFF),
)

_SEMANTIC_REVIEW_CRITERIA: tuple[ReviewCriterion, ...] = (
    ReviewCriterion(
        key="process_orientation",
        instruction=(
            "Describe operations on data and decisions in their working context. "
            "Use declarative definitions only for brief introductions."
        ),
    ),
    ReviewCriterion(
        key="concrete_agents",
        instruction=(
            "Make people or concrete services perform actions. Remove intention, "
            "knowledge, judgment, or agency assigned to abstractions."
        ),
    ),
    ReviewCriterion(
        key="context_and_deixis",
        instruction=(
            "Supply nearby scope and clear referents. Include evidence where the "
            "claim needs support, so the passage shows the relevant context."
        ),
    ),
    ReviewCriterion(
        key="deliberative_voice",
        instruction=(
            "Explain choices in a deliberative voice. Describe the related "
            "operations and consequences in their local scope."
        ),
    ),
    ReviewCriterion(
        key="plain_english",
        instruction=(
            "Use idiomatic American English with natural subject-verb-object order. "
            "Reject periodic, garden-path, fragmentary, or mechanically balanced "
            "sentences."
        ),
    ),
    ReviewCriterion(
        key="current_context",
        instruction=(
            "Keep comments and durable documentation in the present tense. Remove "
            "first-person narration and copied user wording. Remove missing "
            "conversation context, change-history framing, suspicious denials, and "
            "editorial spin."
        ),
    ),
    ReviewCriterion(
        key="sentence_relationships",
        instruction=(
            "Use hypotaxis and typographic structure to clarify relationships. Prefer "
            "asyndeton where conjunctions add no meaning. Reject loose clause chains, "
            "restricted relatives, default triads, and synonym cycling."
        ),
    ),
    ReviewCriterion(
        key="rhetorical_restraint",
        instruction=(
            "Reject overconfident identity claims, universals, negative "
            "counterfactuals, metaphorical engineering language, and rhetoric that "
            "announces or dramatizes the answer."
        ),
    ),
    ReviewCriterion(
        key="contextual_vocabulary",
        instruction=(
            "Replace metaphorical engineering uses of artifact, bring up, buy, "
            "contract, earn, flight, hug, land, mint, name, noun, own, pin, reach, "
            "seam, see, shape, ship, sit, smoke, speak, sugar, surface, touch, triage, "
            "verb, want, weld, and wire with literal descriptions."
        ),
    ),
    ReviewCriterion(
        key="rewrite_method",
        instruction=(
            "When a passage fails, rewrite it from the intended meaning. Build a new "
            "passage instead of rearranging the same sentence pattern."
        ),
    ),
)


def _mask_html_code(text: str) -> str:
    """Mask generated HTML code elements while preserving source offsets."""

    def mask(match: re.Match[str]) -> str:
        return "".join(
            character if character.isspace() else " " for character in match[0]
        )

    return _HTML_CODE_RE.sub(mask, text)


class FindingKind(StrEnum):
    """Closed set of rewrite categories emitted by this rule."""

    ABSTRACT_AGENT = "abstract_agent"
    COMMA_CHAIN = "comma_chain"
    COUNTING_CLAIM = "counting_claim"
    IDENTITY_FORMULA = "identity_formula"
    NEGATIVE_ADDENDUM = "negative_addendum"
    ONE_AS_ARTICLE = "one_as_article"
    POLYSYNDETON = "polysyndeton"
    PROCESS_SUBJECT = "process_subject"
    PROHIBITED_TERM = "prohibited_term"
    QUESTION_HEADING = "question_heading"
    QUESTION_WORD_STATEMENT = "question_word_statement"
    RESTRICTED_RELATIVE = "restricted_relative"
    SEMICOLON_OVERUSE = "semicolon_overuse"
    SIGNPOST = "signpost"
    TYPOGRAPHIC_CHARACTER = "typographic_character"


@dataclass(frozen=True)
class _Finding:
    """One style-guide match with its source span and rewrite category."""

    start: int
    end: int
    match: str
    kind: FindingKind


@dataclass
class SubstantialProseStyleRuleConfig(RuleConfig):
    """Configuration for the substantial-prose style-guide rule."""

    min_words: int = field(
        metadata={
            "description": (
                "Minimum prose word count required before strict style-guide "
                "checks run."
            )
        }
    )
    penalty: int = field(
        metadata={"description": "Penalty applied to each recorded style finding."}
    )
    record_cap: int = field(
        metadata={
            "description": (
                "Maximum number of individual style findings returned for one "
                "document; all findings still contribute to the count."
            )
        }
    )
    context_window_chars: int = field(
        metadata={
            "description": (
                "Half-width in characters of the source context returned with "
                "each finding."
            )
        }
    )


def _trimmed_finding(
    text: str,
    start: int,
    end: int,
    kind: FindingKind,
) -> _Finding:
    """Build a finding after trimming whitespace from a matched span."""
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return _Finding(start=start, end=end, match=text[start:end], kind=kind)


def _regex_findings(
    text: str,
    pattern: re.Pattern[str],
    kind: FindingKind,
    *,
    group: str | int = 0,
) -> list[_Finding]:
    """Return trimmed findings for every match from one compiled pattern."""
    findings: list[_Finding] = []
    for match in pattern.finditer(text):
        start, end = match.span(group)
        findings.append(_trimmed_finding(text, start, end, kind))
    return findings


def _character_findings(text: str) -> list[_Finding]:
    """Return findings for prohibited dashes and decorative symbols."""
    findings: list[_Finding] = []
    for index, character in enumerate(text):
        codepoint = ord(character)
        is_decorative = any(
            start <= codepoint <= end for start, end in _DECORATIVE_CODEPOINT_RANGES
        )
        if character in {"\u2013", "\u2014"} or is_decorative:
            findings.append(
                _Finding(
                    start=index,
                    end=index + 1,
                    match=character,
                    kind=FindingKind.TYPOGRAPHIC_CHARACTER,
                )
            )
    return findings


def _polysyndeton_findings(text: str) -> list[_Finding]:
    """Return sentence findings containing three or more uses of ``and``."""
    findings: list[_Finding] = []
    for sentence_match in _SENTENCE_SPAN_RE.finditer(text):
        sentence = sentence_match.group(0)
        if len(_AND_RE.findall(sentence)) < 3:
            continue
        findings.append(
            _trimmed_finding(
                text,
                sentence_match.start(),
                sentence_match.end(),
                FindingKind.POLYSYNDETON,
            )
        )
    return findings


def _question_word_statement_findings(text: str) -> list[_Finding]:
    """Return declarative sentences that begin with a question word."""
    findings: list[_Finding] = []
    for sentence_match in _SENTENCE_SPAN_RE.finditer(text):
        start = sentence_match.start()
        end = sentence_match.end()
        if end < len(text) and text[end] == "?":
            continue
        finding = _trimmed_finding(
            text,
            start,
            end,
            FindingKind.QUESTION_WORD_STATEMENT,
        )
        if _QUESTION_WORD_RE.match(finding.match) is not None:
            findings.append(finding)
    return findings


def _semicolon_findings(text: str) -> list[_Finding]:
    """Return each semicolon after two free occurrences in a document."""
    positions = [index for index, character in enumerate(text) if character == ";"]
    return [
        _Finding(
            start=index,
            end=index + 1,
            match=";",
            kind=FindingKind.SEMICOLON_OVERUSE,
        )
        for index in positions[2:]
    ]


def _collect_findings(document: AnalysisDocument) -> list[_Finding]:
    """Collect deterministic style-guide findings from prose-only text."""
    text = _mask_html_code(document.text_with_markdown_code_masked)
    findings = [
        *_regex_findings(text, _PROHIBITED_TERM_RE, FindingKind.PROHIBITED_TERM),
        *_regex_findings(text, _SIGNPOST_RE, FindingKind.SIGNPOST),
        *_regex_findings(
            text,
            _OPENING_SIGNPOST_RE,
            FindingKind.SIGNPOST,
            group="claim",
        ),
        *_regex_findings(text, _QUESTION_HEADING_RE, FindingKind.QUESTION_HEADING),
        *_regex_findings(
            text,
            _COUNTING_CLAIM_RE,
            FindingKind.COUNTING_CLAIM,
            group="claim",
        ),
        *_regex_findings(text, _ABSTRACT_AGENT_RE, FindingKind.ABSTRACT_AGENT),
        *_regex_findings(
            text,
            _PROCESS_SUBJECT_RE,
            FindingKind.PROCESS_SUBJECT,
            group="claim",
        ),
        *_regex_findings(text, _ONE_AS_ARTICLE_RE, FindingKind.ONE_AS_ARTICLE),
        *_regex_findings(
            text,
            _RESTRICTED_RELATIVE_RE,
            FindingKind.RESTRICTED_RELATIVE,
        ),
        *_regex_findings(
            text,
            _NEGATIVE_ADDENDUM_RE,
            FindingKind.NEGATIVE_ADDENDUM,
            group="claim",
        ),
        *_regex_findings(text, _IDENTITY_FORMULA_RE, FindingKind.IDENTITY_FORMULA),
        *_regex_findings(text, _PAREN_COMMA_CHAIN_RE, FindingKind.COMMA_CHAIN),
        *_character_findings(text),
        *_polysyndeton_findings(text),
        *_question_word_statement_findings(text),
        *_semicolon_findings(text),
    ]
    unique = {
        (finding.start, finding.end, finding.kind): finding for finding in findings
    }
    return sorted(unique.values(), key=lambda finding: (finding.start, finding.end))


def _advice(finding: _Finding) -> str:
    """Return direct rewrite guidance for one finding category."""
    if finding.kind is FindingKind.PROHIBITED_TERM:
        return f"Replace '{finding.match}' with the specific object, action, or date."
    if finding.kind is FindingKind.SIGNPOST:
        return f"Remove '{finding.match}' and state the point directly."
    if finding.kind is FindingKind.QUESTION_HEADING:
        return "Rewrite the heading as a direct noun phrase."
    if finding.kind is FindingKind.COUNTING_CLAIM:
        return "Replace the number-led slogan with a direct description."
    if finding.kind is FindingKind.ABSTRACT_AGENT:
        return "Describe the operation and the data it changes without humanizing an abstraction."
    if finding.kind is FindingKind.PROCESS_SUBJECT:
        return "Name the actor, then describe the operation performed on the data."
    if finding.kind is FindingKind.ONE_AS_ARTICLE:
        return "Use 'a', 'an', or 'the' unless the number itself matters."
    if finding.kind is FindingKind.RESTRICTED_RELATIVE:
        return (
            "Rewrite the restricted relative clause as a direct sentence or subpoint."
        )
    if finding.kind is FindingKind.NEGATIVE_ADDENDUM:
        return "Rewrite the negative addendum as a direct account of the operation."
    if finding.kind is FindingKind.POLYSYNDETON:
        return (
            "Split the actions or use typographic structure instead of repeated 'and'."
        )
    if finding.kind is FindingKind.IDENTITY_FORMULA:
        return "Replace the identity formula with a concrete description."
    if finding.kind is FindingKind.QUESTION_WORD_STATEMENT:
        return "Rewrite the declarative phrase without a question-word opening."
    if finding.kind is FindingKind.COMMA_CHAIN:
        return "Move the comma chain into a list or separate clauses."
    if finding.kind is FindingKind.SEMICOLON_OVERUSE:
        return "Split the clause or use typographic structure instead of another semicolon."
    if finding.kind is FindingKind.TYPOGRAPHIC_CHARACTER:
        return "Replace the decorative character with plain punctuation or text."
    raise ValueError(f"Unknown finding kind: {finding.kind}")


class SubstantialProseStyleRule(Rule[SubstantialProseStyleRuleConfig]):
    """Apply strict, deterministic style checks to substantial prose."""

    name = "substantial_prose_style"
    count_key = "substantial_prose_style"
    level = RuleLevel.PASSAGE

    def example_violations(self) -> list[str]:
        """Return substantial samples that should trigger style findings."""
        return [
            (
                "Straight answer: the workflow knows which record belongs here. "
                "The operator opens the report after the import finishes. She "
                "compares each row with its source record and notes missing values. "
                "The reviewer checks the totals, asks about unclear entries, and "
                "records the answer beside the affected row. The author updates the "
                "report after review, then sends it back for a final check."
            )
        ]

    def example_non_violations(self) -> list[str]:
        """Return a substantial sample written in direct process-oriented prose."""
        return [
            (
                "The operator opens the report after the import finishes. She "
                "compares each row with its source record and notes missing values. "
                "The reviewer checks the totals, asks the author about unclear "
                "entries, and records the answer beside the affected row. The author "
                "updates the report after that review, then sends it back for a final "
                "accuracy check."
            )
        ]

    def forward(self, document: AnalysisDocument) -> RuleResult:
        """Apply strict checks after the document reaches the configured size."""
        if document.word_count < self.config.min_words:
            return RuleResult()

        findings = _collect_findings(document)
        violations = [
            Violation(
                rule=self.name,
                match=finding.match,
                context=context_around(
                    document.text,
                    finding.start,
                    finding.end,
                    width=self.config.context_window_chars,
                ),
                penalty=self.config.penalty,
                start=finding.start,
                end=finding.end,
            )
            for finding in findings[: self.config.record_cap]
        ]
        advice = [_advice(finding) for finding in findings[: self.config.record_cap]]
        return RuleResult(
            violations=violations,
            advice=advice,
            count_deltas={self.count_key: len(findings)} if findings else {},
            review_requirements=[
                ReviewRequirement(
                    rule=self.name,
                    reason=(
                        "The deterministic pass covers observable patterns. A writing "
                        "agent judges each semantic criterion before claiming "
                        "conformance."
                    ),
                    criteria=_SEMANTIC_REVIEW_CRITERIA,
                )
            ],
        )

    def _fit(
        self, samples: list[str], labels: list[Label] | None
    ) -> SubstantialProseStyleRuleConfig:
        """Fit penalty strength from style-finding prevalence."""
        positive_samples, negative_samples = self._split_fit_samples(samples, labels)
        if not positive_samples:
            return self.config

        def has_match(sample: str) -> bool:
            document = AnalysisDocument.from_text(sample)
            return document.word_count >= self.config.min_words and bool(
                _collect_findings(document)
            )

        return SubstantialProseStyleRuleConfig(
            min_words=self.config.min_words,
            penalty=fit_penalty_contrastive(
                base_penalty=self.config.penalty,
                positive_matches=sum(has_match(sample) for sample in positive_samples),
                positive_total=len(positive_samples),
                negative_matches=sum(has_match(sample) for sample in negative_samples),
                negative_total=len(negative_samples),
            ),
            record_cap=self.config.record_cap,
            context_window_chars=self.config.context_window_chars,
        )
