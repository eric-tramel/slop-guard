# slop-guard v0.3.1

v0.3.1 adds stronger AI-slop detection coverage and credits the community contribution from **SinatrasC** (PR #20).

## Highlights

- Added 14 words and 48 phrase patterns to the slop phrase/word inventories, across adjectives, verbs, nouns, and hedges.
- Introduced five passage-level rules, each with fit support and packaged examples:
  - `CopulaChainRule`
  - `ExtremeSentenceRule`
  - `ClosingAphorismRule`
  - `ParagraphBalanceRule`
  - `ParagraphCVRule`
- Updated defaults so the new rule set is available in standard runs of both the CLI and MCP entry point.

## Why it matters

- Better vocabulary coverage helps the analyzer flag AI-styled phrasing that was under-detected by older defaults.
- New structural passage checks catch formulaic patterning around copula chains, sentence length, ending aphorisms, and paragraph rhythm.

## Attribution

This release is based on the community PR #20 by @SinatrasC.
