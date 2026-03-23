---
name: qa
description: Black-box QA audit of slop-guard across MCP, CLI, fit, docs, and agent workflows. Files GitHub issues for real problems found.
argument-hint: "[focus-area or 'all']"
---

# Slop-Guard QA Audit

Black-box QA of slop-guard through its public interfaces only. Do not read source files or tests to find bugs — discover issues by using the product as an agent or user would.

Launch parallel subagents per testing angle. File genuine issues with `gh issue create`. If `$ARGUMENTS` specifies a focus area (`mcp`, `cli`, `fit`, `docs`, or `workflows`), run only that angle. Otherwise run all 5 in parallel.

## Setup

1. Read `README.md` for documented behavior.
2. If `mcp__slop_guard__*` tools are available, fetch their schemas via tool search.
3. Fetch open issues to avoid duplicates:
   ```bash
   gh issue list --repo eric-tramel/slop-guard --limit 100 --state open --json number,title,body,labels
   ```
4. Prefer local QA fixtures if present. Otherwise create temp files under `/tmp/slop-guard-qa`. Do not write throwaway files into the repo.

Pass the open issues list into every subagent prompt.

## Testing Angles

### 1. MCP Agent Interface (`mcp`)

Is the MCP surface clear, consistent, and useful for an agent?

- Tool descriptions, parameter clarity, distinction between `check_slop` and `check_slop_file`
- JSON output structure: `score`, `band`, `violations`, `counts`, `advice`, `file`
- Edge cases: short text, empty strings, unicode, markdown, code fences, long inputs
- Missing/unreadable file paths
- Response size and parseability
- Cross-check MCP vs CLI JSON output on the same input

Issue prefix: `mcp: `

### 2. CLI UX (`cli`)

Does `uv run sg` behave predictably?

- All flags from `sg --help`: `--json`, `--verbose`, `--quiet`, `--threshold`, `--score-only`, `--counts`, `--config`, `--version`
- Input modes: file paths, inline text, stdin (`-`), multiple inputs
- Exit codes: 0 (pass), 1 (threshold fail), 2 (error)
- Stdout/stderr separation for scripting
- Path-vs-inline-text ambiguity
- Missing files, bad config paths

Issue prefix: `cli: `

### 3. Fit Workflow (`fit`)

Can a user fit a custom rule config from docs alone?

- Legacy shorthand: `sg-fit TARGET_CORPUS OUTPUT`
- Multi-input mode with `--output`
- All input formats: `.jsonl`, `.txt`, `.md`
- `--negative-dataset`, `--no-calibration`, `--init`
- Error cases: malformed JSONL, missing `text` field, invalid `label`, missing files, unsupported suffixes
- Round-trip: is the fitted JSONL immediately usable with `sg -c`?

Issue prefix: `fit: `

### 4. Docs and Onboarding (`docs`)

Do install flows and docs match actual behavior?

- Install paths: `uvx slop-guard`, `uv tool install slop-guard`, `uv run sg`
- MCP setup snippets for Claude and Codex
- Custom config examples
- Whether documented commands, flags, and tool names match reality

Issue prefix: `docs: `

### 5. End-to-End Workflows (`workflows`)

Does slop-guard compose well for real agent work?

1. Lint prose via MCP or CLI, assess whether advice is actionable enough to drive a rewrite
2. Lint a real file via `check_slop_file` or `sg README.md`
3. CI gating with `sg -t 60 ...` — is the output machine-parseable?
4. Compare MCP and CLI results on the same input

Focus on cross-surface consistency, scoring coherence, and whether the product actually improves agent writing workflows.

Issue prefix: `workflow: `

## Issue Filing

Before filing, check every open issue — skip if same root cause, same behavior, or strict subset. When in doubt, don't file. If related but distinct, add `Related: #N`.

Use existing repo labels (`bug`, `enhancement`, `documentation`, etc.). Each issue body must include:

1. Summary (user/agent perspective)
2. Reproduction steps (exact commands or tool calls)
3. Expected vs observed behavior
4. Severity: `critical` / `high` / `medium` / `low`
5. Surface: `mcp` / `cli` / `fit` / `docs` / `workflow`
6. `Generated with [Claude Code](https://claude.com/claude-code)`

## Summary Report

After all angles complete, compile results grouped by severity. Include: total issues filed, findings already tracked, what works well, what was not tested, and whether MCP tools were available.
