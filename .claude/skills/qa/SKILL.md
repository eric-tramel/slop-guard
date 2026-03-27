---
name: qa
description: Black-box QA audit of slop-guard across MCP, CLI, fit, docs, agent workflows, and writing-effectiveness. Files GitHub issues for real problems found.
argument-hint: "[focus-area or 'all']"
---

# Slop-Guard QA Audit

Black-box QA of slop-guard through its public interfaces only. Do not read source files or tests to find bugs — discover issues by using the product as an agent or user would.

Launch parallel subagents per testing angle. File genuine issues with `gh issue create`. If `$ARGUMENTS` specifies a focus area (`mcp`, `cli`, `fit`, `docs`, `workflows`, or `effectiveness`), run only that angle. Otherwise run all 6 in parallel.

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

### 6. Writing Effectiveness (`effectiveness`)

Does slop-guard's feedback actually make an agent produce better writing? This angle tests the quality of the feedback loop — not whether the tool runs correctly, but whether following its guidance leads to measurably improved prose.

**Method:** Act as an agent that writes, scores, interprets advice, rewrites, and rescores. Evaluate every step for friction, ambiguity, and actual improvement.

#### 6a. Advice Actionability

For each test, write a paragraph in a specific register (technical docs, blog post, marketing copy, academic summary, casual explanation), score it, then attempt to follow every piece of advice literally.

- Is each advice string specific enough to know *what* to change? ("Replace 'crucial' — what specifically do you mean?" is good; a vague suggestion would be bad)
- Does the advice tell you *how* to fix it, or only *that* something is wrong?
- When multiple violations overlap in the same sentence, does the combined advice make sense or contradict itself?
- Are there violations with no corresponding advice entry? (The advice array should cover every fixable issue)
- Does any advice lead you toward a *different* slop pattern? (e.g., replacing a slop word with another slop word)

#### 6b. Feedback Loop Convergence

Run iterative rewrite cycles and track whether the score converges upward:

1. Write 3-5 paragraphs of deliberately sloppy AI-style prose (heavy on slop words, uniform rhythm, bold-bullet structures, contrast pairs)
2. Score via `check_slop` or `sg --json`
3. Rewrite following *only* the advice array — no independent judgment
4. Rescore the rewrite
5. Repeat until score stabilizes or advice is empty

Evaluate:
- Does the score improve monotonically with each cycle? If not, what caused a regression?
- How many cycles to reach `clean` band? (Should be 1-2 for light, 2-3 for moderate)
- Does the advice array shrink each cycle, or do new violations appear as old ones are fixed?
- Is there a score plateau where advice remains but following it doesn't move the score? What's blocking?
- At convergence, does the text actually read well — or has it been "optimized" into something sterile/awkward?

#### 6c. Score Sensitivity and Proportionality

Test whether scores reflect actual writing quality differences:

- Write two versions of the same content: one natural, one AI-sloppy. Do scores separate cleanly?
- Take clean prose (human-written, score >80) and introduce one slop word. How much does the score drop? Is the penalty proportional?
- Take a short text (<50 words) vs a long text (~500 words) with the same density of violations. Are scores comparable?
- Does the concentration penalty feel right? Write text with 1 contrast pair (should be mild) vs 5 contrast pairs (should be harsh). Check that scoring reflects this.

#### 6d. Advice Interpretation by an Agent

Simulate how an LLM agent would parse and act on the JSON output:

- Given the violations array with `match` and `context` fields, can you locate the exact position in the original text to edit? Is the 60-char context window sufficient?
- When advice says "Replace X — what specifically do you mean?", does the agent have enough context from the surrounding violations to pick a good replacement?
- Are the `counts` useful for triage? (e.g., "12 slop_words vs 1 rhythm issue" — should the agent focus on vocabulary first?)
- If the agent can only make one edit, does the output help prioritize which fix has the highest impact? (Penalties vary: -10 for ai_disclosure vs -1 for a slop word)
- Does the band label (`light`, `moderate`, etc.) help the agent decide whether to rewrite or accept?

#### 6e. Register Sensitivity

Test whether slop-guard handles different writing registers fairly:

- **Technical documentation:** Do legitimate technical terms get false-positived as slop? (e.g., "framework", "robust", "scalable" in a systems design context)
- **Persuasive/marketing copy:** This register naturally uses more emphatic language. Does slop-guard penalize it unfairly, or does it correctly distinguish marketing voice from AI slop?
- **Academic writing:** Hedging language ("arguably", "perhaps", "it seems") is standard in academic prose. Does the weasel rule over-penalize legitimate scholarly register?
- **Conversational/casual:** Does informal writing score better simply because it avoids formal slop patterns, even if it's low-quality?

For each register, write a *good* example and a *sloppy* example. The tool should score good writing higher regardless of register.

#### 6f. Rewrite Quality Assessment

After the agent completes a rewrite cycle, evaluate the *output* text:

- Does the rewritten text preserve the original meaning and intent?
- Has the rewrite introduced awkward phrasing or unnatural constructions to dodge rules?
- Is the rewritten text something a human editor would accept, or does it feel "linted" — technically clean but lifeless?
- Compare: original sloppy text vs rewritten text vs hand-written alternative. Where does the tool-guided rewrite land on that spectrum?

File issues for patterns where following advice consistently produces worse prose, where scores don't reflect quality, where the feedback loop stalls, or where the interface makes it hard for an agent to act on feedback.

Issue prefix: `effectiveness: `

## Issue Filing

Before filing, check every open issue — skip if same root cause, same behavior, or strict subset. When in doubt, don't file. If related but distinct, add `Related: #N`.

Use existing repo labels (`bug`, `enhancement`, `documentation`, etc.). Each issue body must include:

1. Summary (user/agent perspective)
2. Reproduction steps (exact commands or tool calls)
3. Expected vs observed behavior
4. Severity: `critical` / `high` / `medium` / `low`
5. Surface: `mcp` / `cli` / `fit` / `docs` / `workflow` / `effectiveness`
6. `Generated with [Claude Code](https://claude.com/claude-code)`

For `effectiveness` issues: use the `enhancement` label unless the issue describes advice that actively misleads (then `bug`). Include the original text, the advice received, the rewrite attempt, and before/after scores. Concrete examples are mandatory — do not file vague "advice could be better" issues.

## Summary Report

After all angles complete, compile results grouped by severity. Include: total issues filed, findings already tracked, what works well, what was not tested, and whether MCP tools were available.
