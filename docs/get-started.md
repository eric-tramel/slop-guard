---
icon: lucide/rocket
---

# Get started

`slop-guard` works as a command-line linter and as an MCP server for coding agents. The fastest way to try it is to run the CLI once with `uvx`.

## Run once

```bash
uvx --from slop-guard sg README.md
```

That command downloads the current release, runs the linter, and exits without installing a long-lived tool.

## Install the CLI

If you want a persistent command, install the package as a `uv` tool:

```bash
uv tool install slop-guard
sg README.md
```

You can pin a specific release when reproducibility matters:

```bash
uv tool install slop-guard==0.4.1
```

## Gate prose in CI

Use a threshold when you want prose checks to fail the build:

```bash
sg -t 60 README.md docs/**/*.md
```

Add `-v` to inspect individual hits, or `-j` when you want JSON output for scripts.

## Pick a rule preset

slop-guard ships two rule presets. The default is `ai_slop` (the rules that target model-generated tells). Pass `-c` with the bundled `writing_quality.jsonl` when you want the opinionated style checks instead.

Resolve the bundled paths once:

```bash
DEFAULT_PATH=$(python -c 'from importlib.resources import files; print(files("slop_guard.rules").joinpath("assets/default.jsonl"))')
WQ_PATH=$(python -c 'from importlib.resources import files; print(files("slop_guard.rules").joinpath("assets/writing_quality.jsonl"))')
```

Run the default `ai_slop` preset:

```bash
sg README.md
# equivalent to:
sg -c "$DEFAULT_PATH" README.md
```

Run the `writing_quality` preset:

```bash
sg -c "$WQ_PATH" README.md
```

Run both presets in one pass by concatenating the JSONLs:

```bash
cat "$DEFAULT_PATH" "$WQ_PATH" > all_rules.jsonl
sg -c all_rules.jsonl README.md
```

Each violation in the JSON output carries a `category` field set to the preset that registered the rule, and the result includes `category_counts` aggregating violations per category.

## Work from source

From a local checkout, `uv run` exposes the same entry points without publishing a package first:

```bash
uv run sg README.md
uv run slop-guard
uv run sg-fit --help
```

If you are working on this repository's documentation site, these project targets cover the Zensical workflow:

```bash
make docs-serve
make docs-build
make docs-check
```
