---
icon: lucide/list-checks
title: Rule library
description: Catalog of the rules that slop-guard runs on every check.
---

# Rule library

`slop-guard` ships a pipeline of small, independently scored rules. Each rule targets one formulaic pattern, flags the exact matching spans, and contributes a penalty toward the final score.

The default pipeline runs **24 rules** across four scopes. Open a card to read the full rule page, including example violations, default thresholds, and a link to the source file.

## Word rules

Single-token checks. These are the cheapest rules and fire on individual AI-associated words.

<div class="sg-rule-grid">
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./slop-word/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Slop Word</span></div>
    <p class="sg-rule-card__summary">Detect overused AI-associated slop words.</p>
  </a>
</div>
</div>

## Sentence rules

One sentence at a time. Catches canned phrases, disclosures, tone markers, and templated pivots.

<div class="sg-rule-grid">
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./slop-phrase/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Slop Phrase</span></div>
    <p class="sg-rule-card__summary">Detect stock slop phrases and transition templates.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./tone-marker/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Tone Marker</span></div>
    <p class="sg-rule-card__summary">Detect AI-style tone markers and opener tells.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./weasel-phrase/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Weasel Phrase</span></div>
    <p class="sg-rule-card__summary">Detect unattributed weasel phrases.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./ai-disclosure/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">AI Disclosure</span></div>
    <p class="sg-rule-card__summary">Detect direct AI self-disclosure statements.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./placeholder/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Placeholder</span></div>
    <p class="sg-rule-card__summary">Detect unfinished placeholder markers.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./contrast-pair/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Contrast Pair</span></div>
    <p class="sg-rule-card__summary">Detect repeated contrast constructions that stage a binary opposition.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./intrasentence-keyword-bold/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Intrasentence Keyword Bold</span></div>
    <p class="sg-rule-card__summary">Detect short, mid-sentence keyword bold spans (LLM emphasis tic).</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./setup-resolution/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Setup Resolution</span></div>
    <p class="sg-rule-card__summary">Detect setup-resolution rhetorical flips.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./pithy-fragment/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Pithy Fragment</span></div>
    <p class="sg-rule-card__summary">Detect short evaluative pivot fragments.</p>
  </a>
</div>
</div>

## Paragraph rules

Adjacent-line structure. Catches bullet runs, blockquotes, horizontal rules, and listicle layouts.

<div class="sg-rule-grid">
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./structural-pattern/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Structural Pattern</span></div>
    <p class="sg-rule-card__summary">Detect listicle-like structural patterns in paragraphs.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./bullet-density/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Bullet Density</span></div>
    <p class="sg-rule-card__summary">Detect bullet-heavy document formatting.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./blockquote-density/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Blockquote Density</span></div>
    <p class="sg-rule-card__summary">Detect excessive thesis-style blockquote usage.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./bold-term-bullet-run/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Bold Term Bullet Run</span></div>
    <p class="sg-rule-card__summary">Detect runs of bullets that start with bold terms.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./horizontal-rule-overuse/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Horizontal Rule Overuse</span></div>
    <p class="sg-rule-card__summary">Detect overuse of horizontal rule separators.</p>
  </a>
</div>
</div>

## Passage rules

Whole-document signals. Catches rhythm, density, and repetition across the full text.

<div class="sg-rule-grid">
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./rhythm/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Rhythm</span></div>
    <p class="sg-rule-card__summary">Detect monotonous sentence-length rhythm.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./em-dash-density/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Em Dash Density</span></div>
    <p class="sg-rule-card__summary">Detect overuse of em dashes across a passage.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./colon-density/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Colon Density</span></div>
    <p class="sg-rule-card__summary">Detect elaboration-colon overuse in prose passages.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./phrase-reuse/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Phrase Reuse</span></div>
    <p class="sg-rule-card__summary">Detect repeated long n-gram phrase reuse.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./copula-chain/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Copula Chain</span></div>
    <p class="sg-rule-card__summary">Detect high copula-sentence density - an encyclopedic AI chain pattern.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./extreme-sentence/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Extreme Sentence</span></div>
    <p class="sg-rule-card__summary">Detect extremely long run-on sentences.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./closing-aphorism/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Closing Aphorism</span></div>
    <p class="sg-rule-card__summary">Detect moralizing or generalizing closing sentences.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./paragraph-balance/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Paragraph Balance</span></div>
    <p class="sg-rule-card__summary">Detect suspiciously uniform paragraph lengths.</p>
  </a>
</div>
<div class="sg-rule-card">
  <a class="sg-rule-card__link" href="./paragraph-cv/">
    <div class="sg-rule-card__head"><span class="sg-rule-card__title">Paragraph CV</span></div>
    <p class="sg-rule-card__summary">Detect suspiciously uniform paragraph lengths.</p>
  </a>
</div>
</div>
