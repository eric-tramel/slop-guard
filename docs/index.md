---
icon: lucide/book-open-text
---

# slop-guard docs

`slop-guard` is a rule-based prose linter for formulaic AI writing. It scores text from 0 to 100, points to the exact spans that pulled the score down, and returns direct advice for the rewrite.

This site is versioned by release. Use the selector in the header to move between tagged releases and `dev (main)` when you want the current state of the default branch.

## Hello world

Run the CLI once with `uvx`:

```bash
uvx --from slop-guard sg README.md
```

That command installs the published package into a temporary environment, lints the file, and prints a compact score line. When you need the exact matches and rewrite guidance, rerun it with `-v`:

```bash
uvx --from slop-guard sg -v README.md
```

Continue with [Get Started](get-started.md) for installation and local workflows, or jump to [Agents](agents.md) for Codex and Claude Code setup.
