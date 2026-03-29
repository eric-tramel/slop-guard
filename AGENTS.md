# Agent Instructions

[Slop-Guard](https://github.com/eric-tramel/slop-guard) is a programmatic tool for giving linter-style feedback to an agent on English writing style.

## Development

### UV

The project uses `uv`. Always use `uv` for python command line actions.

```
uv run ...
uv run --with dependency ...
```

### Git Workflow

* When asked for a new feature, bug fix, or other code-specific work, check out a new branch on a new git worktree.
Use `gh` for interactions with GitHub.
* Create a commit and push a PR with a full description that fills out the following sections.
```
## Description

[... a paragraph decription of what the PR is ...]

## Why?

[... a paragraph about why this PR needed to exist ...]

## Usage / Demonstration

[... can be as long as necessary, should include code blocks ...]

## Verification

[ ... what was done to verify the PR ... ]

## Issues

[ ... list of Issue items related or that are closed by the PR ... ] 

```
* The PR title should be a simple sentence describing what it is.
* Don't mark PRs as draft when creating them.
* Don't include any AI agent authorship claims (e.g. "[codex]..." or "Authored by: ..." etc.)

### Python Style

* Full Google style docstrings for modules, classes, and functions.
* Strong types in 3.11+ python conventions.
* Use TypeAlias to define compositions of types.
* Loud errors, no "defensive" coding.
* Optimized for time-efficient computation, even at the cost of legibility.
* Favor composition over monoliths.

## Code Invariants

* **No dead code.** When a refactor makes something unused, delete it in the same commit. After any API move, grep for all callers — including `benchmark/`, tests, and imports — and update them.
* **MCP return types.** Tools must return typed structured payloads (`dict[str, Any]`), not `str`. Error paths must raise `ToolError`, not return plain strings.
* **`sg-fit` requires contrastive data.** Positive-only fitting drives all positive scores to zero. Always require both positives and negatives.
* **Do not commit `uv.lock` changes** unless you explicitly added or removed a dependency — `uv run` dirties it as a side effect.
* **Each agent works in its own isolated worktree.** If a worktree is shared, never revert or overwrite another agent's uncommitted changes.

## Writing and Documentation

* Always run slop-guard MCP tools (or use `sg` CLI) to ensure your documentation is high-quality.
* This rule applies to: README, any docs/, PRs, issues, etc. Any human-facing writing.

