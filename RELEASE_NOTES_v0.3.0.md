# slop-guard v0.3.0

v0.3.0 turns rule fitting into a first-class workflow and makes runtime configuration easier across both CLI and MCP usage. If you are upgrading from v0.2.0, the headline is simple: you can now train and ship your own rule settings with `sg-fit`.

## Highlights

- New `sg-fit` command to fit rule configs from real corpora and export JSONL settings.
- Contrastive fitting support across all default rules with optional post-fit calibration.
- Configurable rule pipelines for both `sg` and `slop-guard` MCP server via `-c/--config`.
- Clearer CLI surface for scoring (`-s/--score-only`) and rule-config loading (`-c/--config`).

## New in v0.3.0: `sg-fit`

`sg-fit` is a dedicated fitting CLI for generating tuned rule settings from your own datasets.

### Core workflow

```bash
# Legacy shorthand
sg-fit TARGET_CORPUS OUTPUT

# Multi-input mode
sg-fit --output rules.fitted.jsonl data/*.jsonl docs/**/*.md
```

### What it supports

- `.jsonl`, `.txt`, and `.md` inputs
- Positive datasets (default label `1` when omitted)
- Optional negative datasets via `--negative-dataset` (normalized to label `0`)
- Initial config seeding via `--init`
- Optional faster fitting via `--no-calibration`

This makes it practical to fit settings for your team, export a JSONL config, and run that exact profile in both CLI and MCP environments.

## Interface changes since v0.2.0

These are the user-facing behavior changes to call out when upgrading:

- `sg -c/--config` now means "load rule config JSONL".
- Score-only output moved to `sg -s/--score-only`.
- `slop-guard` MCP server also supports `-c/--config` for custom rule settings.
- Removed legacy `--glob` argument behavior in `sg`; use shell expansion (`**/*.md`, etc.) instead.

## Why this release matters

v0.2.0 introduced the fit API foundation. v0.3.0 operationalizes it:

- Every default rule now participates in empirical fitting.
- Pipeline fit supports optional contrastive calibration.
- Fitted configs are portable JSONL artifacts that can be versioned and reused.

## Upgrade quickstart

```bash
# Pin this release
uvx slop-guard==0.3.0

# Fit a custom rule profile
sg-fit data.jsonl rules.fitted.jsonl

# Use fitted settings in CLI
sg -c rules.fitted.jsonl draft.md

# Use fitted settings in MCP server
uvx slop-guard==0.3.0 -c /path/to/rules.fitted.jsonl
```
