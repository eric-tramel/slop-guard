"""Analyzer configuration defaults for slop-guard."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Hyperparameters:
    """Tunable thresholds, caps, and penalties used by the analyzer."""

    concentration_alpha: float = 2.5
    decay_lambda: float = 0.04
    claude_categories: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"contrast_pairs", "pithy_fragment", "setup_resolution"}
        )
    )

    context_window_chars: int = 60
    short_text_word_count: int = 10

    repeated_ngram_min_n: int = 4
    repeated_ngram_max_n: int = 8
    repeated_ngram_min_count: int = 3

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
    intrasentence_keyword_bold_penalty: int = -2
    intrasentence_keyword_bold_record_cap: int = 5
    intrasentence_keyword_bold_advice_min: int = 3
    intrasentence_keyword_bold_max_words: int = 5
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

    density_words_basis: float = 1000.0
    score_min: int = 0
    score_max: int = 100
    band_clean_min: int = 80
    band_light_min: int = 60
    band_moderate_min: int = 40
    band_heavy_min: int = 20


DEFAULT_HYPERPARAMETERS = Hyperparameters()
