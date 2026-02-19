# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp"]
# ///
"""MCP server for prose linting — detects AI slop patterns in text.

Single tool: check_slop(text) returns a JSON score with specific violations.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from functools import partial, reduce
from pathlib import Path
from typing import Callable

from mcp.server.fastmcp import FastMCP

MCP_SERVER_NAME = "slop-guard"

# ---------------------------------------------------------------------------
# Hyperparameters
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Hyperparameters:
    """Tunable thresholds, caps, and penalties used by the analyzer."""

    # Scoring curve and concentration
    concentration_alpha: float = 2.5
    decay_lambda: float = 0.04
    claude_categories: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"contrast_pairs", "pithy_fragment", "setup_resolution"}
        )
    )

    # Short-text behavior
    context_window_chars: int = 60
    short_text_word_count: int = 10

    # Repeated n-gram detection
    repeated_ngram_min_n: int = 4
    repeated_ngram_max_n: int = 8
    repeated_ngram_min_count: int = 3

    # Rule penalties and thresholds
    slop_word_penalty: int = -2
    slop_phrase_penalty: int = -3
    structural_bold_header_min: int = 3
    structural_bold_header_penalty: int = -5
    structural_bullet_run_min: int = 6
    structural_bullet_run_penalty: int = -3
    triadic_record_cap: int = 5
    triadic_penalty: int = -1
    triadic_advice_min: int = 3
    tone_penalty: int = -3
    sentence_opener_penalty: int = -2
    weasel_penalty: int = -2
    ai_disclosure_penalty: int = -10
    placeholder_penalty: int = -5
    rhythm_min_sentences: int = 5
    rhythm_cv_threshold: float = 0.3
    rhythm_penalty: int = -5
    em_dash_words_basis: float = 150.0
    em_dash_density_threshold: float = 1.0
    em_dash_penalty: int = -3
    contrast_record_cap: int = 5
    contrast_penalty: int = -1
    contrast_advice_min: int = 2
    setup_resolution_record_cap: int = 5
    setup_resolution_penalty: int = -3
    colon_words_basis: float = 150.0
    colon_density_threshold: float = 1.5
    colon_density_penalty: int = -3
    pithy_max_sentence_words: int = 6
    pithy_record_cap: int = 3
    pithy_penalty: int = -2
    bullet_density_threshold: float = 0.40
    bullet_density_penalty: int = -8
    blockquote_min_lines: int = 3
    blockquote_free_lines: int = 2
    blockquote_cap: int = 4
    blockquote_penalty_step: int = -3
    bold_bullet_run_min: int = 3
    bold_bullet_run_penalty: int = -5
    horizontal_rule_min: int = 4
    horizontal_rule_penalty: int = -3
    phrase_reuse_record_cap: int = 5
    phrase_reuse_penalty: int = -1

    # Score normalization and banding
    density_words_basis: float = 1000.0
    score_min: int = 0
    score_max: int = 100
    band_clean_min: int = 80
    band_light_min: int = 60
    band_moderate_min: int = 40
    band_heavy_min: int = 20


HYPERPARAMETERS = Hyperparameters()


@dataclass(frozen=True)
class Violation:
    """Canonical violation record emitted by rule checks."""

    rule: str
    match: str
    context: str
    penalty: int

    def to_payload(self) -> dict[str, object]:
        """Serialize a typed violation for tool output."""
        return {
            "type": "Violation",
            "rule": self.rule,
            "match": self.match,
            "context": self.context,
            "penalty": self.penalty,
        }


@dataclass
class RuleContext:
    """Mutable scratch context for legacy mutating rule implementations."""

    text: str
    word_count: int
    sentences: list[str]
    advice: list[str]
    counts: dict[str, int]
    hyperparameters: Hyperparameters


@dataclass(frozen=True)
class AnalysisContext:
    """Read-only context shared by functional rule wrappers."""

    text: str
    word_count: int
    sentences: list[str]
    hyperparameters: Hyperparameters


@dataclass
class RuleResult:
    """Output emitted by a single rule application."""

    violations: list[Violation]
    advice: list[str]
    count_deltas: dict[str, int]


@dataclass(frozen=True)
class AnalysisState:
    """Immutable analysis accumulator used by the functional pipeline."""

    violations: tuple[Violation, ...]
    advice: tuple[str, ...]
    counts: dict[str, int]

    @classmethod
    def initial(cls, counts: dict[str, int]) -> "AnalysisState":
        """Construct an empty analysis state with initial category counts."""
        return cls(violations=(), advice=(), counts=dict(counts))

    def merge(
        self,
        violations: list[Violation],
        advice: list[str],
        count_deltas: dict[str, int],
    ) -> "AnalysisState":
        """Return a new state with appended outputs and incremented counts."""
        merged_counts = dict(self.counts)
        for key, delta in count_deltas.items():
            if delta:
                merged_counts[key] = merged_counts.get(key, 0) + delta
        return AnalysisState(
            violations=self.violations + tuple(violations),
            advice=self.advice + tuple(advice),
            counts=merged_counts,
        )


LegacyRulePrototype = Callable[[list[str], list[Violation], RuleContext], None]
RulePrototype = Callable[[list[str], AnalysisContext], RuleResult]

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# --- 1. Slop words ---

_SLOP_ADJECTIVES = [
    "crucial", "groundbreaking", "pivotal", "paramount", "seamless", "holistic",
    "multifaceted", "meticulous", "profound", "comprehensive", "invaluable",
    "notable", "noteworthy", "game-changing", "revolutionary", "pioneering",
    "visionary", "formidable", "quintessential", "unparalleled",
    "stunning", "breathtaking", "captivating", "nestled", "robust",
    "innovative", "cutting-edge", "impactful",
]

_SLOP_VERBS = [
    "delve", "delves", "delved", "delving", "embark", "embrace", "elevate",
    "foster", "harness", "unleash", "unlock", "orchestrate", "streamline",
    "transcend", "navigate", "underscore", "showcase", "leverage",
    "ensuring", "highlighting", "emphasizing", "reflecting",
]

_SLOP_NOUNS = [
    "landscape", "tapestry", "journey", "paradigm", "testament", "trajectory",
    "nexus", "symphony", "spectrum", "odyssey", "pinnacle", "realm", "intricacies",
]

_SLOP_HEDGE = [
    "notably", "importantly", "furthermore", "additionally", "particularly",
    "significantly", "interestingly", "remarkably", "surprisingly", "fascinatingly",
    "moreover", "however", "overall",
]

_ALL_SLOP_WORDS = _SLOP_ADJECTIVES + _SLOP_VERBS + _SLOP_NOUNS + _SLOP_HEDGE

# Single compiled regex: word boundary, case-insensitive, alternation
_SLOP_WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in _ALL_SLOP_WORDS) + r")\b",
    re.IGNORECASE,
)

# --- 2. Slop phrases ---

_SLOP_PHRASES_LITERAL = [
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
    # Rule 10: Menu-of-options / offer to rewrite
    "if you want, i can",
    "i can adapt this",
    "i can make this",
    "here are some options",
    "here are a few options",
    "would you prefer",
    "shall i",
    "if you'd like, i can",
    "i can also",
    # Rule 11: Restatement transition phrases
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
]

_SLOP_PHRASES_RE_LIST: list[re.Pattern[str]] = [
    re.compile(re.escape(p), re.IGNORECASE) for p in _SLOP_PHRASES_LITERAL
]

# "not just X, but" regex pattern
_NOT_JUST_BUT_RE = re.compile(
    r"not (just|only) .{1,40}, but (also )?", re.IGNORECASE
)

# --- 3. Structural patterns ---

# **Bold.** or **Bold:** followed by more text
_BOLD_HEADER_RE = re.compile(r"\*\*[^*]+[.:]\*\*\s+\S")

# Bullet lines: - item, * item, or 1. item
_BULLET_LINE_RE = re.compile(r"^(\s*[-*]\s|\s*\d+\.\s)")

# Triadic: "X, Y, and Z"
_TRIADIC_RE = re.compile(r"\w+, \w+, and \w+", re.IGNORECASE)

# --- 4. Tone markers ---

_META_COMM_PATTERNS = [
    re.compile(r"would you like", re.IGNORECASE),
    re.compile(r"let me know if", re.IGNORECASE),
    re.compile(r"as mentioned", re.IGNORECASE),
    re.compile(r"i hope this", re.IGNORECASE),
    re.compile(r"feel free to", re.IGNORECASE),
    re.compile(r"don't hesitate to", re.IGNORECASE),
]

_FALSE_NARRATIVITY_PATTERNS = [
    re.compile(r"then something interesting happened", re.IGNORECASE),
    re.compile(r"this is where things get interesting", re.IGNORECASE),
    re.compile(r"that's when everything changed", re.IGNORECASE),
]

# --- 4b. Sentence-opener tells ---

_SENTENCE_OPENER_PATTERNS = [
    re.compile(r"(?:^|[.!?]\s+)(certainly[,! ])", re.IGNORECASE | re.MULTILINE),
    re.compile(r"(?:^|[.!?]\s+)(absolutely[,! ])", re.IGNORECASE | re.MULTILINE),
]

# --- 4c. Weasel phrases ---

_WEASEL_PATTERNS = [
    re.compile(r"\bsome critics argue\b", re.IGNORECASE),
    re.compile(r"\bmany believe\b", re.IGNORECASE),
    re.compile(r"\bexperts suggest\b", re.IGNORECASE),
    re.compile(r"\bstudies show\b", re.IGNORECASE),
    re.compile(r"\bsome argue\b", re.IGNORECASE),
    re.compile(r"\bit is widely believed\b", re.IGNORECASE),
    re.compile(r"\bresearch suggests\b", re.IGNORECASE),
]

# --- 4d. AI self-disclosure ---

_AI_DISCLOSURE_PATTERNS = [
    re.compile(r"\bas an ai\b", re.IGNORECASE),
    re.compile(r"\bas a language model\b", re.IGNORECASE),
    re.compile(r"\bi don't have personal\b", re.IGNORECASE),
    re.compile(r"\bi cannot browse\b", re.IGNORECASE),
    re.compile(r"\bup to my last training\b", re.IGNORECASE),
    re.compile(r"\bas of my (last |knowledge )?cutoff\b", re.IGNORECASE),
    re.compile(r"\bi'm just an? ai\b", re.IGNORECASE),
]

# --- 4e. Placeholder text ---

_PLACEHOLDER_RE = re.compile(
    r"\[insert [^\]]*\]|\[describe [^\]]*\]|\[url [^\]]*\]|\[your [^\]]*\]|\[todo[^\]]*\]",
    re.IGNORECASE,
)

# --- 5. Rhythm ---

_SENTENCE_SPLIT_RE = re.compile(r"[.!?][\"'\u201D\u2019)\]]*(?:\s|$)")

# --- 6. Em dash ---

_EM_DASH_RE = re.compile(r"\u2014| -- ")

# --- 7. "X, not Y" contrast pattern ---

_CONTRAST_PAIR_RE = re.compile(r"\b(\w+), not (\w+)\b")

# --- 7b. Setup-and-resolution ("This isn't X. It's Y.") ---

# Form A: "This isn't X. It's Y." — pronoun + negative verb + content + separator + positive restatement
_SETUP_RESOLUTION_A_RE = re.compile(
    r"\b(this|that|these|those|it|they|we)\s+"
    r"(isn't|aren't|wasn't|weren't|doesn't|don't|didn't|hasn't|haven't|won't|can't|couldn't|shouldn't"
    r"|is\s+not|are\s+not|was\s+not|were\s+not|does\s+not|do\s+not|did\s+not"
    r"|has\s+not|have\s+not|will\s+not|cannot|could\s+not|should\s+not)\b"
    r".{0,80}[.;:,]\s*"
    r"(it's|they're|that's|he's|she's|we're|it\s+is|they\s+are|that\s+is|this\s+is"
    r"|these\s+are|those\s+are|he\s+is|she\s+is|we\s+are|what's|what\s+is"
    r"|the\s+real|the\s+actual|instead|rather)",
    re.IGNORECASE,
)

# Form B: "It's not X. It's Y." — positive contraction + "not" + content + separator + positive restatement
_SETUP_RESOLUTION_B_RE = re.compile(
    r"\b(it's|that's|this\s+is|they're|he's|she's|we're)\s+not\b"
    r".{0,80}[.;:,]\s*"
    r"(it's|they're|that's|he's|she's|we're|it\s+is|they\s+are|that\s+is|this\s+is"
    r"|these\s+are|those\s+are|what's|what\s+is|the\s+real|the\s+actual|instead|rather)",
    re.IGNORECASE,
)

# --- 8. Colon density (elaboration colons) ---

# Matches a colon followed by space + lowercase letter (mid-sentence elaboration)
_ELABORATION_COLON_RE = re.compile(r": [a-z]")
# Fenced code block removal (greedy across lines)
_FENCED_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
# URL colon exclusion (http: or https:)
_URL_COLON_RE = re.compile(r"https?:")
# Markdown header line
_MD_HEADER_LINE_RE = re.compile(r"^\s*#", re.MULTILINE)
# JSON-like colon contexts
_JSON_COLON_RE = re.compile(r': ["{\[\d]|: true|: false|: null')

# --- 9. Pithy evaluative fragments ---

_PITHY_PIVOT_RE = re.compile(r",\s+(?:but|yet|and|not|or)\b", re.IGNORECASE)

# --- 12. Bullet density ---

_BULLET_DENSITY_RE = re.compile(r"^\s*[-*]\s|^\s*\d+[.)]\s", re.MULTILINE)

# --- 13. Blockquote-as-thesis ---

_BLOCKQUOTE_LINE_RE = re.compile(r"^>", re.MULTILINE)

# --- 14. Bold-term bullet runs ---

_BOLD_TERM_BULLET_RE = re.compile(r"^\s*[-*]\s+\*\*|^\s*\d+[.)]\s+\*\*")

# --- 15. Horizontal rule overuse ---

_HORIZONTAL_RULE_RE = re.compile(r"^\s*(?:---+|\*\*\*+|___+)\s*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _context_around(
    text: str,
    start: int,
    end: int,
    width: int | None = None,
    hyperparameters: Hyperparameters = HYPERPARAMETERS,
) -> str:
    """Extract ~width chars of surrounding text centered on [start, end]."""
    if width is None:
        width = hyperparameters.context_window_chars

    mid = (start + end) // 2
    half = width // 2
    ctx_start = max(0, mid - half)
    ctx_end = min(len(text), mid + half)
    snippet = text[ctx_start:ctx_end].replace("\n", " ")
    prefix = "..." if ctx_start > 0 else ""
    suffix = "..." if ctx_end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


def _word_count(text: str) -> int:
    return len(text.split())


def _strip_code_blocks(text: str) -> str:
    """Remove fenced code block contents for analyses that shouldn't count them."""
    return _FENCED_CODE_BLOCK_RE.sub("", text)


_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "is", "it", "that", "this", "with", "as", "by", "from", "was", "were", "are",
    "be", "been", "has", "have", "had", "not", "no", "do", "does", "did", "will",
    "would", "could", "should", "can", "may", "might", "if", "then", "than", "so",
    "up", "out", "about", "into", "over", "after", "before", "between", "through",
    "just", "also", "very", "more", "most", "some", "any", "each", "every", "all",
    "both", "few", "other", "such", "only", "own", "same", "too", "how", "what",
    "which", "who", "when", "where", "why",
})

_PUNCT_STRIP_RE = re.compile(r"^[^\w]+|[^\w]+$")


def _find_repeated_ngrams(
    text: str, hyperparameters: Hyperparameters
) -> list[dict]:
    """Find multi-word phrases repeated 3+ times, returning only the longest.

    Returns a list of dicts with keys: phrase, count, n.
    """
    # Tokenize: split on whitespace, strip punctuation from edges, lowercase
    raw_tokens = text.split()
    tokens = [_PUNCT_STRIP_RE.sub("", t).lower() for t in raw_tokens]
    tokens = [t for t in tokens if t]  # drop empty after stripping

    min_n = hyperparameters.repeated_ngram_min_n
    max_n = hyperparameters.repeated_ngram_max_n

    if len(tokens) < min_n:
        return []

    # Count n-grams for each size
    ngram_counts: dict[tuple[str, ...], int] = {}
    for n in range(min_n, max_n + 1):
        for i in range(len(tokens) - n + 1):
            gram = tuple(tokens[i : i + n])
            ngram_counts[gram] = ngram_counts.get(gram, 0) + 1

    # Filter: repeated occurrences, not all stopwords
    repeated = {
        gram: count
        for gram, count in ngram_counts.items()
        if count >= hyperparameters.repeated_ngram_min_count
        and not all(w in _STOPWORDS for w in gram)
    }

    if not repeated:
        return []

    # Suppress sub-n-grams: if a longer n-gram is repeated, remove shorter
    # n-grams that are fully contained within it.
    to_remove: set[tuple[str, ...]] = set()
    # Sort by length descending so longer grams suppress shorter ones
    sorted_grams = sorted(repeated.keys(), key=len, reverse=True)
    for i, longer in enumerate(sorted_grams):
        longer_str = " ".join(longer)
        for shorter in sorted_grams[i + 1 :]:
            if shorter in to_remove:
                continue
            shorter_str = " ".join(shorter)
            if shorter_str in longer_str and repeated[longer] >= repeated[shorter]:
                to_remove.add(shorter)

    results = []
    for gram in sorted(repeated.keys(), key=lambda g: (-len(g), -repeated[g])):
        if gram not in to_remove:
            results.append({
                "phrase": " ".join(gram),
                "count": repeated[gram],
                "n": len(gram),
            })

    return results


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def _initial_counts() -> dict[str, int]:
    """Create the canonical per-rule counter map used by the analyzer."""
    return {
        "slop_words": 0,
        "slop_phrases": 0,
        "structural": 0,
        "tone": 0,
        "weasel": 0,
        "ai_disclosure": 0,
        "placeholder": 0,
        "rhythm": 0,
        "em_dash": 0,
        "contrast_pairs": 0,
        "colon_density": 0,
        "pithy_fragment": 0,
        "setup_resolution": 0,
        "bullet_density": 0,
        "blockquote_density": 0,
        "bold_bullet_list": 0,
        "horizontal_rules": 0,
        "phrase_reuse": 0,
    }


def _short_text_result(
    word_count: int, counts: dict[str, int], hyperparameters: Hyperparameters
) -> dict:
    """Build the fixed response shape for short text that is skipped."""
    return {
        "score": hyperparameters.score_max,
        "band": "clean",
        "word_count": word_count,
        "violations": [],
        "counts": counts,
        "total_penalty": 0,
        "weighted_sum": 0.0,
        "density": 0.0,
        "advice": [],
    }


def _run_legacy_rule(
    legacy_rule: LegacyRulePrototype,
    lines: list[str],
    context: AnalysisContext,
) -> RuleResult:
    """Run a rule against scratch state and return its emitted deltas."""
    scratch_violations: list[Violation] = []
    scratch_context = RuleContext(
        text=context.text,
        word_count=context.word_count,
        sentences=context.sentences,
        advice=[],
        counts=_initial_counts(),
        hyperparameters=context.hyperparameters,
    )
    legacy_rule(lines, scratch_violations, scratch_context)
    return RuleResult(
        violations=list(scratch_violations),
        advice=list(scratch_context.advice),
        count_deltas=scratch_context.counts,
    )


def _functionalize_rule(legacy_rule: LegacyRulePrototype) -> RulePrototype:
    """Wrap a rule into a pure `(lines, context) -> RuleResult` callable."""

    def _rule(lines: list[str], context: AnalysisContext) -> RuleResult:
        return _run_legacy_rule(legacy_rule, lines, context)

    return _rule


def _run_analysis_pipeline(
    lines: list[str],
    context: AnalysisContext,
    pipeline: list[RulePrototype],
) -> AnalysisState:
    """Execute functional rules with reduce and return the final analysis state."""
    initial_state = AnalysisState.initial(_initial_counts())
    curried_rules = [partial(rule, lines, context) for rule in pipeline]

    def _merge_rule_result(
        state: AnalysisState,
        curried_rule: Callable[[], RuleResult],
    ) -> AnalysisState:
        result = curried_rule()
        return state.merge(
            violations=result.violations,
            advice=result.advice,
            count_deltas=result.count_deltas,
        )

    return reduce(
        _merge_rule_result,
        curried_rules,
        initial_state,
    )


def _collect_slop_word_rule(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect slop words and record one violation per match."""
    text = context.text
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    for m in _SLOP_WORD_RE.finditer(text):
        word = m.group(0)
        violations.append(
            Violation(
                rule="slop_word",
                match=word.lower(),
                context=_context_around(
                    text,
                    m.start(),
                    m.end(),
                    hyperparameters=hyperparameters,
                ),
                penalty=hyperparameters.slop_word_penalty,
            )
        )
        advice.append(f"Replace '{word.lower()}' \u2014 what specifically do you mean?")
        counts["slop_words"] += 1
    return None


def _collect_slop_phrase_rules(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect slop phrases, including the "not just X, but" pattern."""
    text = context.text
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    for pat in _SLOP_PHRASES_RE_LIST:
        for m in pat.finditer(text):
            phrase = m.group(0)
            violations.append(
                Violation(
                    rule="slop_phrase",
                    match=phrase.lower(),
                    context=_context_around(
                        text,
                        m.start(),
                        m.end(),
                        hyperparameters=hyperparameters,
                    ),
                    penalty=hyperparameters.slop_phrase_penalty,
                )
            )
            advice.append(
                f"Cut '{phrase.lower()}' \u2014 just state the point directly."
            )
            counts["slop_phrases"] += 1

    for m in _NOT_JUST_BUT_RE.finditer(text):
        phrase = m.group(0)
        violations.append(
            Violation(
                rule="slop_phrase",
                match=phrase.strip().lower(),
                context=_context_around(
                    text,
                    m.start(),
                    m.end(),
                    hyperparameters=hyperparameters,
                ),
                penalty=hyperparameters.slop_phrase_penalty,
            )
        )
        advice.append(
            f"Cut '{phrase.strip().lower()}' \u2014 just state the point directly."
        )
        counts["slop_phrases"] += 1
    return None


def _collect_structural_patterns(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect structural tics such as bold-header blocks, bullet runs, and triads."""
    text = context.text
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    bold_matches = list(_BOLD_HEADER_RE.finditer(text))
    if len(bold_matches) >= hyperparameters.structural_bold_header_min:
        violations.append(
            Violation(
                rule="structural",
                match="bold_header_explanation",
                context=(
                    f"Found {len(bold_matches)} instances of **Bold.** pattern"
                ),
                penalty=hyperparameters.structural_bold_header_penalty,
            )
        )
        advice.append(
            f"Vary paragraph structure \u2014 {len(bold_matches)} "
            "bold-header-explanation blocks in a row reads as LLM listicle."
        )
        counts["structural"] += 1

    run_length = 0
    for line in lines:
        if _BULLET_LINE_RE.match(line):
            run_length += 1
        else:
            if run_length >= hyperparameters.structural_bullet_run_min:
                violations.append(
                    Violation(
                        rule="structural",
                        match="excessive_bullets",
                        context=(
                            f"Run of {run_length} consecutive bullet lines"
                        ),
                        penalty=hyperparameters.structural_bullet_run_penalty,
                    )
                )
                advice.append(
                    f"Consider prose instead of this {run_length}-item bullet list."
                )
                counts["structural"] += 1
            run_length = 0

    if run_length >= hyperparameters.structural_bullet_run_min:
        violations.append(
            Violation(
                rule="structural",
                match="excessive_bullets",
                context=f"Run of {run_length} consecutive bullet lines",
                penalty=hyperparameters.structural_bullet_run_penalty,
            )
        )
        advice.append(
            f"Consider prose instead of this {run_length}-item bullet list."
        )
        counts["structural"] += 1

    triadic_matches = list(_TRIADIC_RE.finditer(text))
    triadic_count = len(triadic_matches)
    for m in triadic_matches[: hyperparameters.triadic_record_cap]:
        violations.append(
            Violation(
                rule="structural",
                match="triadic",
                context=_context_around(
                    text,
                    m.start(),
                    m.end(),
                    hyperparameters=hyperparameters,
                ),
                penalty=hyperparameters.triadic_penalty,
            )
        )
        counts["structural"] += 1

    if triadic_count >= hyperparameters.triadic_advice_min:
        advice.append(
            f"{triadic_count} triadic structures ('X, Y, and Z') \u2014 "
            "vary your list cadence."
        )
    return None


def _collect_tone_marker_rules(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect tone-level AI tells from meta communication and sentence openers."""
    text = context.text
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    for pat in _META_COMM_PATTERNS:
        for m in pat.finditer(text):
            phrase = m.group(0)
            violations.append(
                Violation(
                    rule="tone",
                    match=phrase.lower(),
                    context=_context_around(
                        text,
                        m.start(),
                        m.end(),
                        hyperparameters=hyperparameters,
                    ),
                    penalty=hyperparameters.tone_penalty,
                )
            )
            advice.append(
                f"Remove '{phrase.lower()}' \u2014 this is a direct AI tell."
            )
            counts["tone"] += 1

    for pat in _FALSE_NARRATIVITY_PATTERNS:
        for m in pat.finditer(text):
            phrase = m.group(0)
            violations.append(
                Violation(
                    rule="tone",
                    match=phrase.lower(),
                    context=_context_around(
                        text,
                        m.start(),
                        m.end(),
                        hyperparameters=hyperparameters,
                    ),
                    penalty=hyperparameters.tone_penalty,
                )
            )
            advice.append(
                f"Cut '{phrase.lower()}' \u2014 announce less, show more."
            )
            counts["tone"] += 1

    for pat in _SENTENCE_OPENER_PATTERNS:
        for m in pat.finditer(text):
            word = m.group(1).strip(" ,!")
            violations.append(
                Violation(
                    rule="tone",
                    match=word.lower(),
                    context=_context_around(
                        text,
                        m.start(),
                        m.end(),
                        hyperparameters=hyperparameters,
                    ),
                    penalty=hyperparameters.sentence_opener_penalty,
                )
            )
            advice.append(
                f"'{word.lower()}' as a sentence opener is an AI tell "
                "\u2014 just make the point."
            )
            counts["tone"] += 1
    return None


def _collect_weasel_phrase_rules(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect weasel phrases that avoid direct attribution."""
    text = context.text
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    for pat in _WEASEL_PATTERNS:
        for m in pat.finditer(text):
            phrase = m.group(0)
            violations.append(
                Violation(
                    rule="weasel",
                    match=phrase.lower(),
                    context=_context_around(
                        text,
                        m.start(),
                        m.end(),
                        hyperparameters=hyperparameters,
                    ),
                    penalty=hyperparameters.weasel_penalty,
                )
            )
            advice.append(
                f"Cut '{phrase.lower()}' \u2014 either cite a source or own the claim."
            )
            counts["weasel"] += 1
    return None


def _collect_ai_disclosure_rules(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect direct model self-disclosure statements."""
    text = context.text
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    for pat in _AI_DISCLOSURE_PATTERNS:
        for m in pat.finditer(text):
            phrase = m.group(0)
            violations.append(
                Violation(
                    rule="ai_disclosure",
                    match=phrase.lower(),
                    context=_context_around(
                        text,
                        m.start(),
                        m.end(),
                        hyperparameters=hyperparameters,
                    ),
                    penalty=hyperparameters.ai_disclosure_penalty,
                )
            )
            advice.append(
                f"Remove '{phrase.lower()}' \u2014 AI self-disclosure in authored "
                "prose is a critical tell."
            )
            counts["ai_disclosure"] += 1
    return None


def _collect_placeholder_rules(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect bracketed placeholder text that indicates unfinished drafting."""
    text = context.text
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    for m in _PLACEHOLDER_RE.finditer(text):
        match_text = m.group(0)
        violations.append(
            Violation(
                rule="placeholder",
                match=match_text.lower(),
                context=_context_around(
                    text,
                    m.start(),
                    m.end(),
                    hyperparameters=hyperparameters,
                ),
                penalty=hyperparameters.placeholder_penalty,
            )
        )
        advice.append(
            f"Remove placeholder '{match_text.lower()}' \u2014 this is unfinished "
            "template text."
        )
        counts["placeholder"] += 1
    return None


def _collect_rhythm_rule(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect low-variance sentence cadence that reads as monotonous."""
    _ = lines
    sentences = context.sentences
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    if len(sentences) < hyperparameters.rhythm_min_sentences:
        return None

    lengths = [len(s.split()) for s in sentences]
    mean = sum(lengths) / len(lengths)
    if mean <= 0:
        return None

    variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    std = math.sqrt(variance)
    cv = std / mean
    if cv < hyperparameters.rhythm_cv_threshold:
        violations.append(
            Violation(
                rule="rhythm",
                match="monotonous_rhythm",
                context=(
                    f"CV={cv:.2f} across {len(sentences)} sentences "
                    f"(mean {mean:.1f} words)"
                ),
                penalty=hyperparameters.rhythm_penalty,
            )
        )
        advice.append(
            f"Sentence lengths are too uniform (CV={cv:.2f}) \u2014 "
            "vary short and long."
        )
        counts["rhythm"] += 1
    return None


def _collect_em_dash_density_rule(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect overuse of em dashes relative to document length."""
    text = context.text
    word_count = context.word_count
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    if word_count <= 0:
        return None

    em_dash_count = len(list(_EM_DASH_RE.finditer(text)))
    ratio_per_150 = (
        em_dash_count / word_count
    ) * hyperparameters.em_dash_words_basis
    if ratio_per_150 > hyperparameters.em_dash_density_threshold:
        violations.append(
            Violation(
                rule="em_dash",
                match="em_dash_density",
                context=(
                    f"{em_dash_count} em dashes in {word_count} words "
                    f"({ratio_per_150:.1f} per 150 words)"
                ),
                penalty=hyperparameters.em_dash_penalty,
            )
        )
        advice.append(
            f"Too many em dashes ({em_dash_count} in {word_count} words) \u2014 "
            "use other punctuation."
        )
        counts["em_dash"] += 1
    return None


def _collect_contrast_pair_rule(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect repeated use of the \"X, not Y\" contrast construction."""
    text = context.text
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    contrast_matches = list(_CONTRAST_PAIR_RE.finditer(text))
    contrast_count = len(contrast_matches)

    for m in contrast_matches[: hyperparameters.contrast_record_cap]:
        matched = m.group(0)
        violations.append(
            Violation(
                rule="contrast_pair",
                match=matched,
                context=_context_around(
                    text,
                    m.start(),
                    m.end(),
                    hyperparameters=hyperparameters,
                ),
                penalty=hyperparameters.contrast_penalty,
            )
        )
        advice.append(
            f"'{matched}' \u2014 'X, not Y' contrast \u2014 consider "
            "rephrasing to avoid the Claude pattern."
        )
        counts["contrast_pairs"] += 1

    if contrast_count >= hyperparameters.contrast_advice_min:
        advice.append(
            f"{contrast_count} 'X, not Y' contrasts \u2014 this is a Claude "
            "rhetorical tic. Vary your phrasing."
        )
    return None


def _collect_setup_resolution_rule(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect setup-resolution flips such as \"This isn't X. It's Y.\"."""
    text = context.text
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    setup_res_recorded = 0
    for pat in (_SETUP_RESOLUTION_A_RE, _SETUP_RESOLUTION_B_RE):
        for m in pat.finditer(text):
            if setup_res_recorded < hyperparameters.setup_resolution_record_cap:
                matched = m.group(0)
                violations.append(
                    Violation(
                        rule="setup_resolution",
                        match=matched,
                        context=_context_around(
                            text,
                            m.start(),
                            m.end(),
                            hyperparameters=hyperparameters,
                        ),
                        penalty=hyperparameters.setup_resolution_penalty,
                    )
                )
                advice.append(
                    f"'{matched}' \u2014 setup-and-resolution is a Claude "
                    "rhetorical tic. Just state the point directly."
                )
                setup_res_recorded += 1
            counts["setup_resolution"] += 1
    return None


def _collect_colon_density_rule(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect overuse of elaboration colons outside code/header contexts."""
    text = context.text
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    stripped_text = _strip_code_blocks(text)
    colon_count = 0

    for line in stripped_text.split("\n"):
        if _MD_HEADER_LINE_RE.match(line):
            continue

        for cm in _ELABORATION_COLON_RE.finditer(line):
            col_pos = cm.start()
            before = line[: col_pos + 1]
            if before.endswith("http:") or before.endswith("https:"):
                continue
            snippet = line[col_pos : col_pos + 10]
            if _JSON_COLON_RE.match(snippet):
                continue
            colon_count += 1

    stripped_word_count = _word_count(stripped_text)
    if stripped_word_count <= 0:
        return None

    colon_ratio_per_150 = (
        colon_count / stripped_word_count
    ) * hyperparameters.colon_words_basis
    if colon_ratio_per_150 > hyperparameters.colon_density_threshold:
        violations.append(
            Violation(
                rule="colon_density",
                match="colon_density",
                context=(
                    f"{colon_count} elaboration colons in {stripped_word_count} "
                    f"words ({colon_ratio_per_150:.1f} per 150 words)"
                ),
                penalty=hyperparameters.colon_density_penalty,
            )
        )
        advice.append(
            f"Too many elaboration colons ({colon_count} in "
            f"{stripped_word_count} words) \u2014 use periods or "
            "restructure sentences."
        )
        counts["colon_density"] += 1
    return None


def _collect_pithy_fragment_rule(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect short evaluative pivots that resemble pithy model fragments."""
    _ = lines
    sentences = context.sentences
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    pithy_count = 0
    for sent in sentences:
        sent_stripped = sent.strip()
        if not sent_stripped:
            continue
        sent_words = sent_stripped.split()
        if len(sent_words) > hyperparameters.pithy_max_sentence_words:
            continue
        if _PITHY_PIVOT_RE.search(sent_stripped):
            if pithy_count < hyperparameters.pithy_record_cap:
                violations.append(
                    Violation(
                        rule="pithy_fragment",
                        match=sent_stripped,
                        context=sent_stripped,
                        penalty=hyperparameters.pithy_penalty,
                    )
                )
                advice.append(
                    f"'{sent_stripped}' \u2014 pithy evaluative fragments are "
                    "a Claude tell. Expand or cut."
                )
            pithy_count += 1
            counts["pithy_fragment"] += 1
    return None


def _collect_bullet_density_rule(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect when a document is dominated by bullet-formatted lines."""
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    non_empty_lines = [line for line in lines if line.strip()]
    total_non_empty = len(non_empty_lines)
    if total_non_empty <= 0:
        return None

    bullet_count = sum(1 for line in non_empty_lines if _BULLET_DENSITY_RE.match(line))
    bullet_ratio = bullet_count / total_non_empty
    if bullet_ratio > hyperparameters.bullet_density_threshold:
        violations.append(
            Violation(
                rule="structural",
                match="bullet_density",
                context=(
                    f"{bullet_count} of {total_non_empty} non-empty lines are "
                    f"bullets ({bullet_ratio:.0%})"
                ),
                penalty=hyperparameters.bullet_density_penalty,
            )
        )
        advice.append(
            f"Over {bullet_ratio:.0%} of lines are bullets \u2014 "
            "write prose instead of lists."
        )
        counts["bullet_density"] += 1
    return None


def _collect_blockquote_density_rule(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect excessive thesis-style blockquote usage outside fenced code."""
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    in_code_block = False
    blockquote_count = 0
    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if not in_code_block and line.startswith(">"):
            blockquote_count += 1

    if blockquote_count >= hyperparameters.blockquote_min_lines:
        excess = blockquote_count - hyperparameters.blockquote_free_lines
        capped = min(excess, hyperparameters.blockquote_cap)
        bq_penalty = hyperparameters.blockquote_penalty_step * capped
        violations.append(
            Violation(
                rule="structural",
                match="blockquote_density",
                context=(
                    f"{blockquote_count} blockquote lines \u2014 Claude uses these "
                    "as thesis statements"
                ),
                penalty=bq_penalty,
            )
        )
        advice.append(
            f"{blockquote_count} blockquotes \u2014 integrate key claims into prose "
            "instead of pulling them out as blockquotes."
        )
        counts["blockquote_density"] += 1
    return None


def _collect_bold_term_bullet_run_rule(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect runs of bullets that all start with bolded lead terms."""
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    bold_bullet_run = 0
    for line in lines:
        if _BOLD_TERM_BULLET_RE.match(line):
            bold_bullet_run += 1
            continue

        if bold_bullet_run >= hyperparameters.bold_bullet_run_min:
            violations.append(
                Violation(
                    rule="structural",
                    match="bold_bullet_list",
                    context=f"Run of {bold_bullet_run} bold-term bullets",
                    penalty=hyperparameters.bold_bullet_run_penalty,
                )
            )
            advice.append(
                f"Run of {bold_bullet_run} bold-term bullets \u2014 this is an LLM "
                "listicle pattern. Use varied paragraph structure."
            )
            counts["bold_bullet_list"] += 1
        bold_bullet_run = 0

    if bold_bullet_run >= hyperparameters.bold_bullet_run_min:
        violations.append(
            Violation(
                rule="structural",
                match="bold_bullet_list",
                context=f"Run of {bold_bullet_run} bold-term bullets",
                penalty=hyperparameters.bold_bullet_run_penalty,
            )
        )
        advice.append(
            f"Run of {bold_bullet_run} bold-term bullets \u2014 this is an LLM "
            "listicle pattern. Use varied paragraph structure."
        )
        counts["bold_bullet_list"] += 1
    return None


def _collect_horizontal_rule_overuse_rule(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect excessive horizontal rule separators."""
    text = context.text
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    hr_count = len(_HORIZONTAL_RULE_RE.findall(text))
    if hr_count >= hyperparameters.horizontal_rule_min:
        violations.append(
            Violation(
                rule="structural",
                match="horizontal_rules",
                context=(
                    f"{hr_count} horizontal rules \u2014 excessive section dividers"
                ),
                penalty=hyperparameters.horizontal_rule_penalty,
            )
        )
        advice.append(
            f"{hr_count} horizontal rules \u2014 section headers alone are "
            "sufficient, dividers are a crutch."
        )
        counts["horizontal_rules"] += 1
    return None


def _collect_phrase_reuse_rule(
    lines: list[str],
    violations: list[Violation],
    context: RuleContext,
) -> None:
    """Detect repeated multi-word phrases and record the longest repeated grams."""
    text = context.text
    advice = context.advice
    counts = context.counts
    hyperparameters = context.hyperparameters

    repeated_ngrams = _find_repeated_ngrams(text, hyperparameters)
    phrase_reuse_recorded = 0
    for ng in repeated_ngrams:
        if phrase_reuse_recorded >= hyperparameters.phrase_reuse_record_cap:
            break
        phrase = ng["phrase"]
        count = ng["count"]
        n = ng["n"]
        violations.append(
            Violation(
                rule="phrase_reuse",
                match=phrase,
                context=f"'{phrase}' ({n}-word phrase) appears {count} times",
                penalty=hyperparameters.phrase_reuse_penalty,
            )
        )
        advice.append(
            f"'{phrase}' appears {count} times \u2014 vary your phrasing "
            "to avoid repetition."
        )
        counts["phrase_reuse"] += 1
        phrase_reuse_recorded += 1
    return None


_apply_slop_word_rule = _functionalize_rule(_collect_slop_word_rule)
_apply_slop_phrase_rules = _functionalize_rule(_collect_slop_phrase_rules)
_apply_structural_patterns = _functionalize_rule(_collect_structural_patterns)
_apply_tone_marker_rules = _functionalize_rule(_collect_tone_marker_rules)
_apply_weasel_phrase_rules = _functionalize_rule(_collect_weasel_phrase_rules)
_apply_ai_disclosure_rules = _functionalize_rule(_collect_ai_disclosure_rules)
_apply_placeholder_rules = _functionalize_rule(_collect_placeholder_rules)
_apply_rhythm_rule = _functionalize_rule(_collect_rhythm_rule)
_apply_em_dash_density_rule = _functionalize_rule(_collect_em_dash_density_rule)
_apply_contrast_pair_rule = _functionalize_rule(_collect_contrast_pair_rule)
_apply_setup_resolution_rule = _functionalize_rule(_collect_setup_resolution_rule)
_apply_colon_density_rule = _functionalize_rule(_collect_colon_density_rule)
_apply_pithy_fragment_rule = _functionalize_rule(_collect_pithy_fragment_rule)
_apply_bullet_density_rule = _functionalize_rule(_collect_bullet_density_rule)
_apply_blockquote_density_rule = _functionalize_rule(
    _collect_blockquote_density_rule
)
_apply_bold_term_bullet_run_rule = _functionalize_rule(
    _collect_bold_term_bullet_run_rule
)
_apply_horizontal_rule_overuse_rule = _functionalize_rule(
    _collect_horizontal_rule_overuse_rule
)
_apply_phrase_reuse_rule = _functionalize_rule(_collect_phrase_reuse_rule)


def _compute_weighted_sum(
    violations: list[Violation], counts: dict[str, int], hyperparameters: Hyperparameters
) -> float:
    """Compute weighted penalties with concentration amplification."""
    weighted_sum = 0.0
    for violation in violations:
        rule = violation.rule
        penalty = abs(violation.penalty)
        cat_count = counts.get(rule, 0) or counts.get(rule + "s", 0)
        count_key = (
            rule
            if rule in hyperparameters.claude_categories
            else (
                rule + "s"
                if (rule + "s") in hyperparameters.claude_categories
                else None
            )
        )
        if (
            count_key
            and count_key in hyperparameters.claude_categories
            and cat_count > 1
        ):
            weight = penalty * (
                1 + hyperparameters.concentration_alpha * (cat_count - 1)
            )
        else:
            weight = penalty
        weighted_sum += weight
    return weighted_sum


def _band_for_score(score: int, hyperparameters: Hyperparameters) -> str:
    """Map a numeric score into the configured severity band."""
    if score >= hyperparameters.band_clean_min:
        return "clean"
    if score >= hyperparameters.band_light_min:
        return "light"
    if score >= hyperparameters.band_moderate_min:
        return "moderate"
    if score >= hyperparameters.band_heavy_min:
        return "heavy"
    return "saturated"


def _deduplicate_advice(advice: list[str]) -> list[str]:
    """Return advice entries preserving first-seen order and removing duplicates."""
    seen_advice: set[str] = set()
    unique_advice: list[str] = []
    for item in advice:
        if item not in seen_advice:
            seen_advice.add(item)
            unique_advice.append(item)
    return unique_advice


def _analyze(text: str, hyperparameters: Hyperparameters) -> dict:
    """Run all slop checks and return score, diagnostics, and advice."""
    word_count = _word_count(text)
    counts = _initial_counts()

    if word_count < hyperparameters.short_text_word_count:
        return _short_text_result(word_count, counts, hyperparameters)

    lines = text.split("\n")
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    context = AnalysisContext(
        text=text,
        word_count=word_count,
        sentences=sentences,
        hyperparameters=hyperparameters,
    )
    pipeline: list[RulePrototype] = [
        _apply_slop_word_rule,
        _apply_slop_phrase_rules,
        _apply_structural_patterns,
        _apply_tone_marker_rules,
        _apply_weasel_phrase_rules,
        _apply_ai_disclosure_rules,
        _apply_placeholder_rules,
        _apply_rhythm_rule,
        _apply_em_dash_density_rule,
        _apply_contrast_pair_rule,
        _apply_setup_resolution_rule,
        _apply_colon_density_rule,
        _apply_pithy_fragment_rule,
        _apply_bullet_density_rule,
        _apply_blockquote_density_rule,
        _apply_bold_term_bullet_run_rule,
        _apply_horizontal_rule_overuse_rule,
        _apply_phrase_reuse_rule,
    ]
    state = _run_analysis_pipeline(lines, context, pipeline)

    total_penalty = sum(violation.penalty for violation in state.violations)
    weighted_sum = _compute_weighted_sum(
        list(state.violations), state.counts, hyperparameters
    )
    density = (
        weighted_sum / (word_count / hyperparameters.density_words_basis)
        if word_count > 0
        else 0.0
    )
    raw_score = hyperparameters.score_max * math.exp(
        -hyperparameters.decay_lambda * density
    )
    score = max(
        hyperparameters.score_min,
        min(hyperparameters.score_max, round(raw_score)),
    )
    band = _band_for_score(score, hyperparameters)

    return {
        "score": score,
        "band": band,
        "word_count": word_count,
        "violations": [violation.to_payload() for violation in state.violations],
        "counts": state.counts,
        "total_penalty": total_penalty,
        "weighted_sum": round(weighted_sum, 2),
        "density": round(density, 2),
        "advice": _deduplicate_advice(list(state.advice)),
    }


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

mcp_server = FastMCP(MCP_SERVER_NAME)


@mcp_server.tool()
def check_slop(text: str) -> str:
    """Analyze text for AI slop patterns.

    Returns a JSON object with a score (0-100), band label, list of specific
    violations with context, and actionable advice for each issue found.
    """
    result = _analyze(text, HYPERPARAMETERS)
    return json.dumps(result, indent=2)


@mcp_server.tool()
def check_slop_file(file_path: str) -> str:
    """Analyze a file for AI slop patterns.

    Reads the file at the given path and runs the same analysis as check_slop.
    Returns a JSON object with a score (0-100), band label, list of specific
    violations with context, and actionable advice for each issue found.
    """
    p = Path(file_path)
    if not p.is_file():
        return json.dumps({"error": f"File not found: {file_path}"})
    try:
        text = p.read_text(encoding="utf-8")
    except Exception as e:
        return json.dumps({"error": f"Could not read file: {e}"})
    result = _analyze(text, HYPERPARAMETERS)
    result["file"] = file_path
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp_server.run()
