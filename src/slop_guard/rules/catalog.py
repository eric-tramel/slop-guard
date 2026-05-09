"""Builtin rule catalog for the packaged slop-guard pipeline."""

DEFAULT_RULE_PATHS: tuple[str, ...] = (
    "slop_guard.rules.word.slop_word.SlopWordRule",
    "slop_guard.rules.sentence.slop_phrase.SlopPhraseRule",
    "slop_guard.rules.paragraph.structural_pattern.StructuralPatternRule",
    "slop_guard.rules.sentence.tone_marker.ToneMarkerRule",
    "slop_guard.rules.sentence.weasel_phrase.WeaselPhraseRule",
    "slop_guard.rules.sentence.ai_disclosure.AIDisclosureRule",
    "slop_guard.rules.sentence.placeholder.PlaceholderRule",
    "slop_guard.rules.passage.rhythm.RhythmRule",
    "slop_guard.rules.passage.em_dash_density.EmDashDensityRule",
    "slop_guard.rules.sentence.contrast_pair.ContrastPairRule",
    "slop_guard.rules.sentence.intrasentence_keyword_bold.IntrasentenceKeywordBoldRule",
    "slop_guard.rules.sentence.setup_resolution.SetupResolutionRule",
    "slop_guard.rules.passage.colon_density.ColonDensityRule",
    "slop_guard.rules.sentence.pithy_fragment.PithyFragmentRule",
    "slop_guard.rules.paragraph.bullet_density.BulletDensityRule",
    "slop_guard.rules.paragraph.blockquote_density.BlockquoteDensityRule",
    "slop_guard.rules.paragraph.bold_term_bullet_run.BoldTermBulletRunRule",
    "slop_guard.rules.paragraph.horizontal_rule_overuse.HorizontalRuleOveruseRule",
    "slop_guard.rules.passage.phrase_reuse.PhraseReuseRule",
    "slop_guard.rules.passage.copula_chain.CopulaChainRule",
    "slop_guard.rules.passage.extreme_sentence.ExtremeSentenceRule",
    "slop_guard.rules.passage.closing_aphorism.ClosingAphorismRule",
    "slop_guard.rules.passage.paragraph_rhythm.ParagraphBalanceRule",
    "slop_guard.rules.passage.paragraph_rhythm.ParagraphCVRule",
)

WRITING_QUALITY_RULE_PATHS: tuple[str, ...] = (
    "slop_guard.rules.word.qualifier_word.QualifierWordRule",
    "slop_guard.rules.word.pretentious_word.PretentiousWordRule",
    "slop_guard.rules.word.ecstatic_adjective.EcstaticAdjectiveRule",
    "slop_guard.rules.sentence.verbose_phrase.VerbosePhraseRule",
    "slop_guard.rules.sentence.throat_clearing.ThroatClearingRule",
    "slop_guard.rules.sentence.over_explanation.OverExplanationRule",
    "slop_guard.rules.sentence.redundant_pair.RedundantPairRule",
    "slop_guard.rules.sentence.cliche_phrase.ClichePhraseRule",
    "slop_guard.rules.sentence.foreign_phrase.ForeignPhraseRule",
    "slop_guard.rules.sentence.passive_voice.PassiveVoiceRule",
    "slop_guard.rules.passage.long_sentence.LongSentenceRule",
    "slop_guard.rules.passage.exclamation_density.ExclamationDensityRule",
    "slop_guard.rules.passage.emoji_in_prose.EmojiInProseRule",
    "slop_guard.rules.paragraph.narrative_heading.NarrativeHeadingRule",
)

ALL_RULE_PATHS: tuple[str, ...] = DEFAULT_RULE_PATHS + WRITING_QUALITY_RULE_PATHS
