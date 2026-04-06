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
