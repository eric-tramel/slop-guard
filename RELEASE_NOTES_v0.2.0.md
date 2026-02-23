# slop-guard v0.2.0

v0.2.0 focuses on packaging, CLI ergonomics, and rule-system internals. If you are upgrading from v0.1.0, this release gives cleaner install paths, a faster pipeline on long inputs, and groundwork for trainable rules.

## Install and launch

slop-guard now fits standard PyPI workflows and the `uvx` execution pattern.

Run without installing:

```bash
uvx slop-guard
```

Install the tool once for local reuse:

```bash
uv tool install slop-guard
```

If you need pinned behavior in scripts:

```bash
uvx slop-guard==0.2.0
```

## New `sg` CLI command

The release adds `sg` as a direct command-line interface for prose linting. It supports file paths and stdin, plus inline text, JSON output, concise output, verbose diagnostics, threshold-based exit codes, and quiet mode for CI filtering.

Examples:

```bash
sg draft.md
sg -v draft.md
sg -j docs/*.md
echo "Sample text" | sg -
```

## Modular rule architecture for reuse

The analyzer is now split into explicit rule modules by level (`word`, `sentence`, `paragraph`, and `passage`) with a shared rule registry and pipeline. This makes it easier to add, swap, or reuse rule components in new tools while preserving the same score and violation model.

## Performance and memory improvements on large inputs

This release reduces hot-path overhead by caching document projections that multiple rules consume, such as token streams and precomputed line flags. It also adds early prefix checks for repeated n-gram detection to avoid expensive full phrase scans when no repeat signal exists. In benchmark runs, the slowest default rule at 10k words is now under 1 ms per forward pass.

## Foundation for fitted rules

Rules now expose a preliminary `.fit(samples, labels)` API with typed input validation and config serialization (`to_dict` / `from_dict`). The default fitting behavior is intentionally conservative today, but the interface lays the groundwork for fitting rule configurations against labeled corpora in upcoming releases.

## Upgrade notes

This release keeps Python `>=3.11` and remains API-compatible at the tool level (`check_slop`, `check_slop_file`, and score payload shape). Existing MCP integrations can move to `uvx slop-guard==0.2.0` for pinned installs.
