# Rhythm Analysis & Sequence-Level Pattern Detection: Design Document

## Motivation

slop-guard currently detects formulaic **word-level** and **phrase-level** patterns (slop words, stock phrases, structural markers). Its single rhythm metric — coefficient of variation (CV) of sentence lengths — catches gross monotony but misses subtler structural patterns that make AI-generated prose feel mechanical.

This document proposes a suite of **rhythm, flow, and paragraph-level** rules that operate at the *sequence* level: analyzing how sentences relate to their neighbors, how paragraphs shape the visual and cognitive experience, and how structural repetition emerges across a document.

---

## Current State

The existing `_collect_rhythm_rule` (line 1007 of `slop_guard.py`) computes:

```
CV = stdev(sentence_word_counts) / mean(sentence_word_counts)
```

- Flags text when CV < 0.3 (too uniform)
- Single penalty, single advice string
- No awareness of local patterns, paragraph structure, or sentence openings

**What it misses:**
- Five consecutive 15-word sentences followed by one 5-word sentence → CV looks fine globally, but the local run is monotonous
- Every sentence starts with "The" → CV is irrelevant to opening patterns
- All paragraphs are exactly 3 sentences → sentence-level CV says nothing about paragraph rhythm
- High autocorrelation (similar-length sentences cluster together) → CV can't detect temporal ordering

---

## Proposed New Rules

### Tier 1: High Signal, Zero Dependencies (Pure Python stdlib)

These rules align with the project's zero-dependency philosophy and provide the highest signal-to-noise ratio.

#### 1. Sentence Opening Repetition

**What it catches:** 3+ consecutive sentences starting with the same word. ProWritingAid and Yoast SEO both flag this threshold. AI text frequently falls into "The X... The Y... The Z..." or "This... This... This..." patterns.

**Algorithm:**
```python
def detect_consecutive_same_starts(sentences, min_run=3):
    first_words = [s.split()[0].lower() for s in sentences if s.split()]
    violations = []
    run_start = 0
    for i in range(1, len(first_words)):
        if first_words[i] != first_words[run_start]:
            if i - run_start >= min_run:
                violations.append((first_words[run_start], i - run_start, run_start))
            run_start = i
    if len(first_words) - run_start >= min_run:
        violations.append((first_words[run_start], len(first_words) - run_start, run_start))
    return violations
```

**Hyperparameters:**
- `opening_repeat_min_run`: 3 (consecutive sentences)
- `opening_repeat_penalty`: -3 per run
- `opening_repeat_min_sentences`: 6 (skip for very short docs)

**Advice:** `"3 consecutive sentences start with '{word}' — vary your sentence openings."`

---

#### 2. First-Word Frequency Concentration

**What it catches:** When any single word accounts for >30% of all sentence openings across the document. Catches global overuse even without consecutive runs.

**Published baselines (ProWritingAid Sentence Structure Report):**
- Subject-first starts: ~72% in published writing
- No single *word* should dominate beyond ~30% (e.g., "The" starting 30%+ of sentences)
- AI text frequently exceeds 85% subject-first and concentrates on "The", "This", "It"

**Algorithm:**
```python
def detect_opening_frequency(sentences, threshold=0.30, min_sentences=8):
    first_words = [s.split()[0].lower() for s in sentences if s.split()]
    if len(first_words) < min_sentences:
        return []
    counts = Counter(first_words)
    total = len(first_words)
    return [(word, count, count/total) for word, count in counts.most_common()
            if count/total >= threshold]
```

**Hyperparameters:**
- `opening_frequency_threshold`: 0.30
- `opening_frequency_penalty`: -2 per offending word
- `opening_frequency_min_sentences`: 8

**Advice:** `"'{word}' starts {pct}% of sentences — diversify openings with prepositional phrases, adverbs, or dependent clauses."`

---

#### 3. Sentence Length Entropy

**What it catches:** Low diversity in sentence length categories. CV can be fooled by a single outlier inflating standard deviation while all other sentences remain uniform. Entropy captures distributional breadth.

**Algorithm:**
```python
def sentence_length_entropy(lengths, bins=((1,8), (9,17), (18,30), (31,999))):
    bin_counts = [0] * len(bins)
    for L in lengths:
        for i, (lo, hi) in enumerate(bins):
            if lo <= L <= hi:
                bin_counts[i] += 1
                break
    total = sum(bin_counts)
    entropy = -sum((c/total) * math.log2(c/total) for c in bin_counts if c > 0)
    return entropy  # max = log2(4) = 2.0
```

**Baselines:**
- Human prose: 1.2–1.8
- Monotonous AI text: < 1.0
- Maximum possible: 2.0 (four bins equally populated)

**Hyperparameters:**
- `entropy_threshold`: 1.0
- `entropy_penalty`: -3
- `entropy_min_sentences`: 8

**Advice:** `"Sentence lengths cluster into too few categories (H={val:.2f}) — mix short punchy sentences with longer complex ones."`

---

#### 4. Sentence Length Autocorrelation

**What it catches:** Temporal clustering — when similar-length sentences appear near each other. Literature on long-range correlations in text (Yang et al., PLOS ONE 2016) shows human writing has near-zero or slightly negative lag-1 autocorrelation (deliberate alternation), while AI text shows positive autocorrelation (similar sentences clustering).

**Algorithm:**
```python
def sentence_length_autocorrelation(lengths, lag=1):
    n = len(lengths)
    if n < lag + 2:
        return 0.0
    mean_len = sum(lengths) / n
    numerator = sum((lengths[i] - mean_len) * (lengths[i+lag] - mean_len) for i in range(n - lag))
    denominator = sum((x - mean_len) ** 2 for x in lengths)
    return numerator / denominator if denominator > 0 else 0.0
```

**Baselines:**
- Human prose: -0.2 to 0.2
- Monotonous AI: > 0.3
- Rigid alternation: < -0.3 (also suspicious)

**Hyperparameters:**
- `autocorrelation_threshold`: 0.35
- `autocorrelation_penalty`: -3
- `autocorrelation_min_sentences`: 10

**Advice:** `"Sentence lengths are too predictable (r={val:.2f}) — adjacent sentences are too similar in length."`

---

#### 5. Burstiness Coefficient

**What it catches:** Whether sentence length variation is naturally "bursty" (clusters of short then clusters of long) or metronomically regular. Complements both CV and autocorrelation.

**Formula:**
```
B = (sigma - mu) / (sigma + mu)
```

**Range:**
- B = -1: perfectly periodic
- B = 0: Poisson process (random)
- B = +1: maximally bursty
- Human writing: -0.3 to 0.1
- AI writing: -0.6 to -0.4 (too regular)

**Hyperparameters:**
- `burstiness_threshold`: -0.4 (flag when B < -0.4)
- `burstiness_penalty`: -2
- `burstiness_min_sentences`: 10

**Advice:** `"Writing rhythm is metronomically regular (B={val:.2f}) — natural prose alternates between short bursts and longer stretches."`

---

#### 6. Consecutive Same-Length-Band Runs

**What it catches:** Local monotony that global metrics miss — runs of 3+ sentences all falling within the same word-count band (e.g., all 12–18 words).

**Algorithm:**
```python
def detect_same_length_runs(lengths, band_width=6, min_run=3):
    violations = []
    run_start = 0
    for i in range(1, len(lengths)):
        band = lengths[run_start] // band_width
        if lengths[i] // band_width == band:
            continue
        if i - run_start >= min_run:
            violations.append((run_start, i - run_start, band * band_width))
        run_start = i
    if len(lengths) - run_start >= min_run:
        band = lengths[run_start] // band_width
        violations.append((run_start, len(lengths) - run_start, band * band_width))
    return violations
```

**Hyperparameters:**
- `length_band_width`: 6 words
- `length_band_min_run`: 3
- `length_band_penalty`: -2 per run

**Advice:** `"{count} consecutive sentences fall in the {lo}–{hi} word range — break the pattern with a notably shorter or longer sentence."`

---

#### 7. Paragraph Length Uniformity

**What it catches:** All paragraphs being suspiciously similar in size — the "every paragraph is exactly 3 sentences" pattern typical of formulaic AI output.

**Algorithm:** Same CV formula as sentence rhythm, applied to paragraph word counts.

**Baselines:**
- Well-written prose: CV 0.30–0.80
- Monotonous AI: CV < 0.25
- Threshold stricter than sentence-level because paragraph variation is naturally higher

**Hyperparameters:**
- `paragraph_cv_threshold`: 0.25
- `paragraph_cv_penalty`: -4
- `paragraph_cv_min_paragraphs`: 4

**Advice:** `"Paragraph sizes are too uniform (CV={val:.2f}) — vary between short emphatic paragraphs and longer developed ones."`

---

#### 8. Wall of Text Detection

**What it catches:** Individual paragraphs exceeding readable length. Research-backed thresholds:

| Context | Optimal Words |
|---------|--------------|
| Web/marketing | 30–60 |
| Blog/business | 60–120 |
| Academic/technical | 120–200 |
| Newspaper | 20–50 |

A threshold of 200 words catches the worst offenders across all genres.

**Hyperparameters:**
- `wall_of_text_threshold`: 200 words
- `wall_of_text_penalty`: -3 per violation

**Advice:** `"Paragraph at position {n} is {wc} words — break it into smaller units for readability."`

---

#### 9. Single-Sentence Paragraph Ratio

**What it catches:** Overuse of pithy standalone paragraphs — used sparingly for emphasis in human writing but overused in AI text (especially Claude).

**Baselines:**
- Human prose: 5–15% single-sentence paragraphs
- Flag above: 25%

**Hyperparameters:**
- `single_sentence_para_threshold`: 0.25
- `single_sentence_para_penalty`: -3
- `single_sentence_para_min_paragraphs`: 5

**Advice:** `"{pct}% of paragraphs are single sentences — develop your ideas into multi-sentence paragraphs."`

---

#### 10. Transition Word Density at Paragraph Starts

**What it catches:** Formulaic paragraph transitions. Human writing uses transition words at ~15–25% of paragraph starts; AI text often exceeds 40%.

**Word list:**
```python
TRANSITION_STARTS = [
    "however", "moreover", "furthermore", "additionally", "consequently",
    "nevertheless", "nonetheless", "meanwhile", "similarly", "likewise",
    "in addition", "in contrast", "on the other hand", "as a result",
    "in particular", "for instance", "for example", "in fact",
    "that said", "to be sure", "of course"
]
```

**Hyperparameters:**
- `transition_start_threshold`: 0.40
- `transition_start_penalty`: -3
- `transition_start_min_paragraphs`: 5

**Advice:** `"{pct}% of paragraphs open with a transition word — let paragraph content create natural flow instead of scaffolding every connection."`

---

#### 11. Information Density Variation

**What it catches:** Uniform information density across sentences. Human writing intentionally alternates between dense (content-heavy) and sparse (connective/transitional) sentences. AI maintains uniform density.

**Algorithm:** Compute content-to-function word ratio per sentence, then measure CV of that ratio.

```python
FUNCTION_WORDS = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                  "has", "have", "had", "do", "does", "did", "will", "would",
                  "could", "should", "can", "may", "might", "shall", "to",
                  "of", "in", "for", "on", "at", "by", "with", "from", "as",
                  "it", "that", "this", "which", "who", "whom", "what",
                  "and", "or", "but", "if", "not", "no", "so", "than"}
```

**Hyperparameters:**
- `info_density_cv_threshold`: 0.15
- `info_density_penalty`: -2
- `info_density_min_sentences`: 8

**Advice:** `"Information density is too uniform across sentences (CV={val:.2f}) — alternate between content-dense and lighter connective sentences."`

---

#### 12. Compression Ratio (Kolmogorov Complexity Proxy)

**What it catches:** Overall text predictability. Highly repetitive/formulaic text compresses more efficiently. Uses `zlib` from Python stdlib.

```python
import zlib

def compression_complexity(text):
    text_bytes = text.encode('utf-8')
    compressed = zlib.compress(text_bytes, level=9)
    return len(compressed) / len(text_bytes)
```

**Baselines:**
- Highly repetitive AI slop: 0.20–0.35
- Average prose: 0.35–0.50
- Rich, varied prose: 0.45–0.60

**Hyperparameters:**
- `compression_threshold`: 0.30
- `compression_penalty`: -3
- `compression_min_words`: 200

**Advice:** `"Text is highly compressible (ratio={val:.2f}) — the phrasing and structure are too repetitive."`

---

### Tier 2: Medium Signal, Approximable Without Heavy NLP

These rules would ideally use a POS tagger (spaCy/NLTK), but can be approximated with a lightweight word-to-category dictionary to preserve the zero-dependency constraint.

#### 13. Approximate POS Opening Pattern Monotony

**Approach:** Maintain a dictionary mapping ~200 common English words to their typical POS category (determiners, pronouns, conjunctions, prepositions, adverbs). Map first 2–3 words of each sentence to approximate POS tags and measure variety via Shannon entropy.

```python
POS_DICT = {
    "the": "DT", "a": "DT", "an": "DT", "this": "DT", "that": "DT",
    "these": "DT", "those": "DT",
    "i": "PRP", "you": "PRP", "he": "PRP", "she": "PRP", "it": "PRP",
    "we": "PRP", "they": "PRP",
    "however": "RB", "moreover": "RB", "furthermore": "RB", "additionally": "RB",
    "in": "IN", "on": "IN", "at": "IN", "for": "IN", "from": "IN",
    "with": "IN", "by": "IN", "about": "IN",
    ...
}
```

**Flag when:** Opening pattern entropy is below threshold (all sentences start with the same grammatical construction even if the actual words differ).

---

#### 14. Paragraph Length Autocorrelation

**What it catches:** Rigid paragraph size patterns — the sequence of paragraph lengths is too predictable.

```python
def paragraph_length_autocorrelation(text):
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    if len(paragraphs) < 4:
        return 0.0
    lengths = [len(p.split()) for p in paragraphs]
    # Same autocorrelation formula as sentence level
```

**Flag when:** |r| > 0.5 with min 5 paragraphs.

---

### Tier 3: Research-Grade (Valuable for Long-Form Text)

These require more data or heavier computation.

#### 15. Hurst Exponent via Detrended Fluctuation Analysis (DFA)

**What it measures:** Long-range correlations in the sentence length time series. Literary texts universally show H = 0.55–0.65 (weak persistence); AI text tends toward H ≈ 0.5 (no memory, like shuffled text).

**When useful:** Documents with 50+ sentences. Not worth computing for short text.

**Reference:** Yang et al., PLOS ONE (2016) — found fractal structure in literary texts with power spectra following 1/f^β scaling.

---

#### 16. Transition Balance Score

**What it measures:** Whether transition words are distributed across categories (additive, adversative, causal, sequential) or concentrated in one type. AI text leans heavily additive ("furthermore," "additionally").

**Algorithm:** Shannon entropy of the transition-type distribution, normalized to [0,1].

---

## Integration Architecture

### Fitting into the Existing Pipeline

All new rules follow the existing pattern at `slop_guard.py:615-648`:

```python
def _collect_new_rule(lines, violations, context):
    """Detect [specific pattern]."""
    # Extract data from context
    sentences = context.sentences
    hyperparameters = context.hyperparameters
    advice = context.advice
    counts = context.counts

    # Compute metric
    # Check threshold
    # Append Violation + advice + increment count
```

Each rule is registered in the pipeline list at line 1558.

### New Hyperparameters

Add to the `Hyperparameters` dataclass (line 29):

```python
# Sentence opening rules
opening_repeat_min_run: int = 3
opening_repeat_penalty: int = -3
opening_repeat_min_sentences: int = 6
opening_frequency_threshold: float = 0.30
opening_frequency_penalty: int = -2
opening_frequency_min_sentences: int = 8

# Enhanced rhythm rules
entropy_threshold: float = 1.0
entropy_penalty: int = -3
entropy_min_sentences: int = 8
autocorrelation_threshold: float = 0.35
autocorrelation_penalty: int = -3
autocorrelation_min_sentences: int = 10
burstiness_threshold: float = -0.4
burstiness_penalty: int = -2
burstiness_min_sentences: int = 10
length_band_width: int = 6
length_band_min_run: int = 3
length_band_penalty: int = -2

# Paragraph rules
paragraph_cv_threshold: float = 0.25
paragraph_cv_penalty: int = -4
paragraph_cv_min_paragraphs: int = 4
wall_of_text_threshold: int = 200
wall_of_text_penalty: int = -3
single_sentence_para_threshold: float = 0.25
single_sentence_para_penalty: int = -3
single_sentence_para_min_paragraphs: int = 5
transition_start_threshold: float = 0.40
transition_start_penalty: int = -3
transition_start_min_paragraphs: int = 5

# Information density
info_density_cv_threshold: float = 0.15
info_density_penalty: int = -2
info_density_min_sentences: int = 8

# Compression
compression_threshold: float = 0.30
compression_penalty: int = -3
compression_min_words: int = 200
```

### AnalysisContext Extensions

The `AnalysisContext` (line 142) needs paragraph-level data:

```python
@dataclass(frozen=True)
class AnalysisContext:
    text: str
    word_count: int
    sentences: list[str]
    paragraphs: list[str]          # NEW
    hyperparameters: Hyperparameters
```

Paragraph splitting in `_analyze()`:
```python
paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
```

---

## Threshold Calibration Table

Summary of all thresholds with baselines from literature:

| Metric | Monotonous | Acceptable | Good | Excellent | Source |
|--------|-----------|------------|------|-----------|--------|
| Sentence CV | < 0.25 | 0.25–0.40 | 0.40–0.60 | 0.60+ | Gary Provost principle |
| Sentence entropy (4 bins) | < 1.0 | 1.0–1.4 | 1.4–1.8 | 1.8+ | Shannon information theory |
| Lag-1 autocorrelation | > 0.35 | 0.15–0.35 | -0.1–0.15 | -0.2–0 | Yang et al. 2016 |
| Burstiness B | < -0.4 | -0.4–-0.2 | -0.2–0.0 | 0.0–0.2 | Goh & Barabasi 2008 |
| Opening word unique ratio | < 0.5 | 0.5–0.7 | 0.7–0.85 | 0.85+ | ProWritingAid benchmarks |
| Paragraph CV | < 0.25 | 0.25–0.45 | 0.45–0.70 | 0.70+ | Writing pedagogy |
| Single-sentence para ratio | > 0.25 | 0.15–0.25 | 0.05–0.15 | < 0.05 | Corpus analysis |
| Transition start ratio | > 0.40 | 0.25–0.40 | 0.10–0.25 | < 0.10 | Corpus analysis |
| Compression ratio | < 0.30 | 0.30–0.40 | 0.40–0.50 | 0.50+ | Kolmogorov complexity |
| Hurst exponent | ~0.50 | 0.50–0.55 | 0.55–0.65 | 0.60–0.75 | Yang et al. 2016 |

---

## Prioritized Implementation Order

1. **Sentence opening repetition** — Highest user-visible signal, trivial to implement
2. **First-word frequency concentration** — Complements #1 with global view
3. **Paragraph length uniformity (CV)** — Opens up the paragraph analysis dimension
4. **Wall of text detection** — Immediately actionable advice
5. **Sentence length entropy** — Strengthens existing rhythm rule
6. **Sentence length autocorrelation** — Captures temporal dimension CV misses
7. **Consecutive same-length-band runs** — Local monotony detection
8. **Single-sentence paragraph ratio** — Claude-specific pattern
9. **Transition start density** — Formulaic paragraph transitions
10. **Burstiness coefficient** — Statistical signal
11. **Information density variation** — Requires function word set
12. **Compression ratio** — Quick holistic metric

---

## References

- Graesser et al. (2004). *Coh-Metrix: Analysis of text on cohesion and language.* Behavior Research Methods.
- Yang et al. (2016). *Long-Range Correlations in Sentence Series from A Story of the Stone.* PLOS ONE.
- Morris & Hirst (1991). *Lexical cohesion computed by thesaural relations.* Computational Linguistics.
- Lu (2010). *Automatic analysis of syntactic complexity in second language writing.* International Journal of Corpus Linguistics.
- Antislop (arXiv:2510.15061). *A Comprehensive Framework for Identifying and Eliminating Repetitive Patterns in Language Models.*
- Gary Provost. *100 Ways to Improve Your Writing.* (Sentence length variation demonstration.)
- ProWritingAid. *Sentence Structure Report* and *Repeats Report* documentation.
- Yoast SEO. *Consecutive Sentences Check.*
- Purdue OWL. *Sentence Variety.*
- Goh & Barabasi (2008). *Burstiness and memory in complex systems.* EPL.
