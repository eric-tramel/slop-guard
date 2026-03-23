---
name: qa
description: Run a comprehensive QA audit of slop-guard from an agent's perspective across its MCP tools, CLI commands, fit workflow, and onboarding docs, and file GitHub issues for real problems found.
argument-hint: "[focus-area or 'all']"
disable-model-invocation: true
---

# Slop-Guard QA Audit

Run a thorough QA audit of slop-guard strictly through its public interfaces:

- `mcp__slop_guard__*` tools, when they are available in the current session
- `uv run sg`
- `uv run sg-fit`
- the documented install and usage flows in `README.md`

This is a black-box QA exercise. Do not read source files or tests to find bugs. Discover issues by using the product the way an agent or user would and by observing outputs, errors, docs, and workflow friction.

Launch parallel subagents, each focused on a different testing angle. Every genuine issue found should be filed on GitHub with `gh issue create`.

If `$ARGUMENTS` specifies a focus area (`mcp`, `cli`, `fit`, `docs`, or `workflows`), run only that agent. Otherwise run all 5 in parallel.

## Before Starting

1. Read the public docs in `README.md`, especially:
   - `Add to Your Agent`
   - `CLI`
   - `Fit Rule Configs`
   - `MCP Tools`
2. If `mcp__slop_guard__*` tools are available, fetch their schemas via tool search and treat that as the MCP source of truth.
3. Optionally use Moraine to search prior `slop-guard` or `zoty` QA conversations for historical context or hypotheses. Prior conversations are not evidence. Every issue must still be reproduced against current behavior.
4. Fetch all open issues and pass them verbatim into every subagent prompt:

```bash
gh issue list --repo eric-tramel/slop-guard --limit 100 --state open --json number,title,body,labels
```

5. Create temporary QA fixtures under `/tmp/slop-guard-qa` or another untracked temp directory. Do not write throwaway QA files into the git worktree unless the user asked for them.

## Testing Angles

Launch one background subagent per angle. Each subagent prompt must include the full open issues list so it can avoid filing duplicates.

All findings must come from public-interface testing. Do not read source code to discover or justify issues.

### 1. MCP Agent Interface (`mcp`)

Focus: Is the MCP surface clear, consistent, and useful for an agent?

- Tool description clarity and distinction between `check_slop` and `check_slop_file`
- Parameter clarity and input expectations
- JSON output structure: `score`, `band`, `violations`, `counts`, `advice`, `file`
- Behavior on short text, empty strings, unicode, markdown, code fences, and long inputs
- File-path ergonomics, missing files, unreadable files
- Response size and parseability for an agent context window
- Compare MCP output against CLI JSON output on the same text when possible

File issues with title prefix: `mcp: `

### 2. CLI UX and Error Handling (`cli`)

Focus: Does `uv run sg` behave predictably for humans and agents?

- File paths, inline text, stdin, and multiple inputs
- `--json`, `--verbose`, `--quiet`, `--threshold`, `--score-only`, `--counts`, and `--config`
- Exit codes: success, threshold failure, and hard errors
- Stdout/stderr clarity and scripting friendliness
- Path-vs-inline-text ambiguity
- Missing files, unreadable files, and bad config paths

File issues with title prefix: `cli: `

### 3. Fit Workflow (`fit`)

Focus: Can an agent successfully fit a custom rule config with `uv run sg-fit`?

- Legacy shorthand: `uv run sg-fit TARGET_CORPUS OUTPUT`
- Multi-input mode with `--output`
- `.jsonl`, `.txt`, and `.md` inputs
- `--negative-dataset` and `--no-calibration`
- Malformed JSONL, missing `text`, invalid `label`, bad globs, missing files, unsupported suffixes
- Whether the fitted JSONL is immediately usable with `uv run sg -c ...`
- Whether a user can succeed from docs alone without code reading

File issues with title prefix: `fit: `

### 4. Onboarding and Install Flows (`docs`)

Focus: Do the README and install flows make the package easy to adopt?

- `uvx slop-guard`
- `uv tool install slop-guard`
- `uv run slop-guard`
- `uv run sg`
- `uv run sg-fit`
- Claude and Codex MCP setup snippets
- Custom `-c /path/to/config.jsonl` examples
- Whether documented tool names, commands, and flags line up with actual behavior

File issues with title prefix: `docs: ` or `onboarding: `

### 5. End-to-End Agent Workflows (`workflows`)

Focus: Does slop-guard compose well for real agent work?

Test these workflows by actually using the product:

1. Analyze inline prose via MCP or CLI JSON, then assess whether the advice is actionable enough to drive a rewrite.
2. Analyze a real markdown file via `check_slop_file` or `uv run sg README.md`.
3. Gate docs with `uv run sg -t 60 ...` and inspect whether the output is CI-friendly.
4. Fit a tiny custom ruleset with `uv run sg-fit`, then lint with `uv run sg -c ...`.
5. Compare MCP and CLI results for the same input when both surfaces are available.

Analyze round-trips, missing metadata, inconsistent scoring, context-window cost, and whether the product actually improves agent writing workflows.

File issues with title prefix: `workflow: ` or `agent-experience: `

## Duplicate Prevention

This is mandatory. Before filing every issue:

1. Compare the finding against every currently open issue title and body.
2. Treat it as a duplicate if it describes the same root cause, the same public behavior, a strict subset of an existing issue, or would require the same fix.
3. If it is already covered, do not file it. Mention it in the final summary as `already tracked by #N`.
4. If it is related but distinct, file it and add a `Related: #N` line in the issue body.
5. When in doubt, do not file.

## Issue Filing Guidelines

Only file genuine friction points, not theoretical concerns or low-signal nitpicks.

Use the existing repo labels instead of inventing a large label taxonomy:

- `bug`
- `enhancement`
- `documentation`
- `question`

Choose the single best existing label for each issue unless a second existing label is clearly warranted.

Each issue body should include:

1. A short summary from the user or agent perspective
2. Exact reproduction steps, including commands or tool calls
3. Expected behavior
4. Observed behavior
5. Severity: `critical`, `high`, `medium`, or `low`
6. Surface: `mcp`, `cli`, `fit`, `docs`, or `workflow`
7. `Generated with [Claude Code](https://claude.com/claude-code)`

Example:

```bash
gh issue create --repo eric-tramel/slop-guard \
  --title "cli: sg misclassifies single-line prose as a file path" \
  --label "bug" \
  --body $'## Summary\n...\n\n## Reproduction\nuv run sg "This sentence has no spaces before punctuation."\n\n## Expected\n...\n\n## Observed\n...\n\n## Severity\nmedium\n\n## Surface\ncli\n\nGenerated with [Claude Code](https://claude.com/claude-code)'
```

## After All Agents Complete

Compile a summary report grouped by severity:

- Critical
- High
- Medium
- Low

Include:

- Total issues filed
- Findings already tracked by existing issues
- What works well
- What was not tested
- Whether MCP tools were available in the session
