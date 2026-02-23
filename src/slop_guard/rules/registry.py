"""Rule registry and default pipeline construction."""

from __future__ import annotations

from typing import TypeAlias

from slop_guard.analysis import Hyperparameters

from .base import Rule, RuleConfig
from .paragraph_level import (
    BlockquoteDensityRule,
    BlockquoteDensityRuleConfig,
    BoldTermBulletRunRule,
    BoldTermBulletRunRuleConfig,
    BulletDensityRule,
    BulletDensityRuleConfig,
    HorizontalRuleOveruseRule,
    HorizontalRuleOveruseRuleConfig,
    StructuralPatternRule,
    StructuralPatternRuleConfig,
)
from .passage_level import (
    ColonDensityRule,
    ColonDensityRuleConfig,
    EmDashDensityRule,
    EmDashDensityRuleConfig,
    PhraseReuseRule,
    PhraseReuseRuleConfig,
    RhythmRule,
    RhythmRuleConfig,
)
from .sentence_level import (
    AIDisclosureRule,
    AIDisclosureRuleConfig,
    ContrastPairRule,
    ContrastPairRuleConfig,
    PithyFragmentRule,
    PithyFragmentRuleConfig,
    PlaceholderRule,
    PlaceholderRuleConfig,
    SetupResolutionRule,
    SetupResolutionRuleConfig,
    SlopPhraseRule,
    SlopPhraseRuleConfig,
    ToneMarkerRule,
    ToneMarkerRuleConfig,
    WeaselPhraseRule,
    WeaselPhraseRuleConfig,
)
from .word_level import SlopWordRule, SlopWordRuleConfig

RuleList: TypeAlias = list[Rule[RuleConfig]]


def build_default_rules(hp: Hyperparameters) -> RuleList:
    """Instantiate the default ordered analyzer rule pipeline."""
    return [
        SlopWordRule(
            SlopWordRuleConfig(
                penalty=hp.slop_word_penalty,
                context_window_chars=hp.context_window_chars,
            )
        ),
        SlopPhraseRule(
            SlopPhraseRuleConfig(
                penalty=hp.slop_phrase_penalty,
                context_window_chars=hp.context_window_chars,
            )
        ),
        StructuralPatternRule(
            StructuralPatternRuleConfig(
                bold_header_min=hp.structural_bold_header_min,
                bold_header_penalty=hp.structural_bold_header_penalty,
                bullet_run_min=hp.structural_bullet_run_min,
                bullet_run_penalty=hp.structural_bullet_run_penalty,
                triadic_record_cap=hp.triadic_record_cap,
                triadic_penalty=hp.triadic_penalty,
                triadic_advice_min=hp.triadic_advice_min,
                context_window_chars=hp.context_window_chars,
            )
        ),
        ToneMarkerRule(
            ToneMarkerRuleConfig(
                tone_penalty=hp.tone_penalty,
                sentence_opener_penalty=hp.sentence_opener_penalty,
                context_window_chars=hp.context_window_chars,
            )
        ),
        WeaselPhraseRule(
            WeaselPhraseRuleConfig(
                penalty=hp.weasel_penalty,
                context_window_chars=hp.context_window_chars,
            )
        ),
        AIDisclosureRule(
            AIDisclosureRuleConfig(
                penalty=hp.ai_disclosure_penalty,
                context_window_chars=hp.context_window_chars,
            )
        ),
        PlaceholderRule(
            PlaceholderRuleConfig(
                penalty=hp.placeholder_penalty,
                context_window_chars=hp.context_window_chars,
            )
        ),
        RhythmRule(
            RhythmRuleConfig(
                min_sentences=hp.rhythm_min_sentences,
                cv_threshold=hp.rhythm_cv_threshold,
                penalty=hp.rhythm_penalty,
            )
        ),
        EmDashDensityRule(
            EmDashDensityRuleConfig(
                words_basis=hp.em_dash_words_basis,
                density_threshold=hp.em_dash_density_threshold,
                penalty=hp.em_dash_penalty,
            )
        ),
        ContrastPairRule(
            ContrastPairRuleConfig(
                penalty=hp.contrast_penalty,
                record_cap=hp.contrast_record_cap,
                advice_min=hp.contrast_advice_min,
                context_window_chars=hp.context_window_chars,
            )
        ),
        SetupResolutionRule(
            SetupResolutionRuleConfig(
                penalty=hp.setup_resolution_penalty,
                record_cap=hp.setup_resolution_record_cap,
                context_window_chars=hp.context_window_chars,
            )
        ),
        ColonDensityRule(
            ColonDensityRuleConfig(
                words_basis=hp.colon_words_basis,
                density_threshold=hp.colon_density_threshold,
                penalty=hp.colon_density_penalty,
            )
        ),
        PithyFragmentRule(
            PithyFragmentRuleConfig(
                penalty=hp.pithy_penalty,
                max_sentence_words=hp.pithy_max_sentence_words,
                record_cap=hp.pithy_record_cap,
            )
        ),
        BulletDensityRule(
            BulletDensityRuleConfig(
                ratio_threshold=hp.bullet_density_threshold,
                penalty=hp.bullet_density_penalty,
            )
        ),
        BlockquoteDensityRule(
            BlockquoteDensityRuleConfig(
                min_lines=hp.blockquote_min_lines,
                free_lines=hp.blockquote_free_lines,
                cap=hp.blockquote_cap,
                penalty_step=hp.blockquote_penalty_step,
            )
        ),
        BoldTermBulletRunRule(
            BoldTermBulletRunRuleConfig(
                min_run_length=hp.bold_bullet_run_min,
                penalty=hp.bold_bullet_run_penalty,
            )
        ),
        HorizontalRuleOveruseRule(
            HorizontalRuleOveruseRuleConfig(
                min_count=hp.horizontal_rule_min,
                penalty=hp.horizontal_rule_penalty,
            )
        ),
        PhraseReuseRule(
            PhraseReuseRuleConfig(
                penalty=hp.phrase_reuse_penalty,
                record_cap=hp.phrase_reuse_record_cap,
                repeated_ngram_min_n=hp.repeated_ngram_min_n,
                repeated_ngram_max_n=hp.repeated_ngram_max_n,
                repeated_ngram_min_count=hp.repeated_ngram_min_count,
            )
        ),
    ]
