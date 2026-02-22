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
When asked for a new feature, bug fix, or other code-specific work, check out a new branch on a new git worktree.
Use `gh` for interactions with GitHub.
Create a commit and push a PR with a full description that fills out the following sections.

```
## Description

## Why?

## Usage / Demonstration

## Test Plan
```

### Python Style

* Google style docstrings for modules, classes, and functions.
* Strong types in 3.11+ python conventions.
* Use TypeAlias to define compositions of types.
* Loud errors, no "defensive" coding.
* Optimized for time-efficient computation, even at the cost of legibility.
* Favor composition over monoliths.

