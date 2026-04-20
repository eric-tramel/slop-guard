---
icon: lucide/shield-check
title: Intrasentence Keyword Bold
description: Detect short, mid-sentence keyword bold spans (LLM emphasis tic).
---

<div class="sg-rule-page" markdown>

<header class="sg-rule-page__header sg-rule-page__header--sentence">
  <div class="sg-rule-page__eyebrow">SENTENCE</div>
  <div class="sg-rule-page__titlebar">
    <h1 class="sg-rule-page__title">Intrasentence Keyword Bold</h1>
    <a class="sg-source-chip" href="https://github.com/eric-tramel/slop-guard/blob/main/src/slop_guard/rules/sentence/intrasentence_keyword_bold.py"><svg class="sg-source-chip__icon" viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false"><path fill="currentColor" d="M12 .5C5.73.5.5 5.73.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56v-2.02c-3.2.7-3.87-1.54-3.87-1.54-.52-1.32-1.28-1.67-1.28-1.67-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.47.11-3.06 0 0 .97-.31 3.18 1.18.92-.26 1.9-.39 2.88-.4.98.01 1.96.14 2.88.4 2.2-1.49 3.17-1.18 3.17-1.18.64 1.59.24 2.77.12 3.06.74.81 1.19 1.84 1.19 3.1 0 4.43-2.69 5.4-5.26 5.68.41.36.78 1.06.78 2.15v3.19c0 .31.21.68.8.56 4.57-1.52 7.85-5.83 7.85-10.91C23.5 5.73 18.27.5 12 .5Z"/></svg><span>source</span></a>
  </div>
  <p class="sg-rule-page__lede" markdown>Detect short, mid-sentence keyword bold spans (LLM emphasis tic).</p>
</header>

<dl class="sg-rule-meta">
  <div class="sg-rule-meta__item"><dt>Class</dt><dd><code>IntrasentenceKeywordBoldRule</code></dd></div>
  <div class="sg-rule-meta__item"><dt>Rule name</dt><dd><code>intrasentence_keyword_bold</code></dd></div>
  <div class="sg-rule-meta__item"><dt>Count key</dt><dd><code>intrasentence_keyword_bold</code></dd></div>
</dl>

## Behavior

<table class="sg-behavior">
  <thead>
    <tr><th class="sg-behavior__th-result">Result</th><th>Input text</th><th>Why</th></tr>
  </thead>
  <tbody>
    <tr class="sg-behavior__row sg-behavior__row--flag"><td class="sg-behavior__result"><span class="sg-status sg-status--flag"><span class="sg-status__dot" aria-hidden="true"></span>Flag</span></td><td><code class="sg-behavior__input">"We need to <strong>carefully consider</strong> all the options before deciding."</code></td><td class="sg-behavior__why">Mid-sentence bold span used as arbitrary keyword emphasis.</td></tr>
    <tr class="sg-behavior__row sg-behavior__row--flag"><td class="sg-behavior__result"><span class="sg-status sg-status--flag"><span class="sg-status__dot" aria-hidden="true"></span>Flag</span></td><td><code class="sg-behavior__input">"The system must remain <strong>highly available</strong> during peak hours."</code></td><td class="sg-behavior__why">Two-word emphasis inserted into otherwise normal prose.</td></tr>
    <tr class="sg-behavior__row sg-behavior__row--pass"><td class="sg-behavior__result"><span class="sg-status sg-status--pass"><span class="sg-status__dot" aria-hidden="true"></span>Pass</span></td><td><code class="sg-behavior__input">"<strong>Note:</strong> make sure to back up your data first."</code></td><td class="sg-behavior__why">Bold acts as a labeled lead-in at the start of the line.</td></tr>
    <tr class="sg-behavior__row sg-behavior__row--pass"><td class="sg-behavior__result"><span class="sg-status sg-status--pass"><span class="sg-status__dot" aria-hidden="true"></span>Pass</span></td><td><code class="sg-behavior__input">"## A section heading without inline emphasis"</code></td><td class="sg-behavior__why">Markdown heading line with no inline bold.</td></tr>
    <tr class="sg-behavior__row sg-behavior__row--pass"><td class="sg-behavior__result"><span class="sg-status sg-status--pass"><span class="sg-status__dot" aria-hidden="true"></span>Pass</span></td><td><code class="sg-behavior__input">"The release shipped on schedule and the team celebrated."</code></td><td class="sg-behavior__why">Plain prose without any bold formatting.</td></tr>
  </tbody>
</table>

## Severity

Low per instance, medium when repeated frequently in one passage.

## Default configuration

<div class="sg-defaults">
  <div class="sg-defaults__item"><span class="sg-defaults__label">advice_min</span><span class="sg-defaults__value">3</span></div>
  <div class="sg-defaults__item"><span class="sg-defaults__label">context_window_chars</span><span class="sg-defaults__value">60</span></div>
  <div class="sg-defaults__item"><span class="sg-defaults__label">max_words</span><span class="sg-defaults__value">5</span></div>
  <div class="sg-defaults__item"><span class="sg-defaults__label">penalty</span><span class="sg-defaults__value">-2</span></div>
  <div class="sg-defaults__item"><span class="sg-defaults__label">record_cap</span><span class="sg-defaults__value">5</span></div>
</div>

## Contributors

<div class="sg-contributors">
  <a class="sg-contrib" href="https://github.com/chris-alexiuk"><img class="sg-contrib__avatar" src="https://github.com/chris-alexiuk.png?size=72" alt="" loading="lazy" width="24" height="24" /><span class="sg-contrib__name">@chris-alexiuk</span></a>
</div>

</div>
