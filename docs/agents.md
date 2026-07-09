---
icon: lucide/bot
---

# Agents

The Claude Code and Codex plugins bundle Slop-Guard's MCP integration and an optional response check. Both use the same local, rule-based analyzer; there are no API calls or model-side judges.

## Install the runtime

The plugins require [uv](https://docs.astral.sh/uv/) and Slop-Guard 0.5.1 or newer installed persistently on `PATH`:

```bash
uv tool install 'slop-guard>=0.5.1'
# Later:
uv tool upgrade slop-guard
```

The bundled MCP server provides two tools:

- `check_slop(text)` analyzes text already held by the client.
- `check_slop_file(file_path)` reads and analyzes a file.

Both return structured diagnostics.

## Claude Code

Add the repository marketplace with the catalog and plugin directory, then install with response checks disabled:

```bash
claude plugin marketplace add eric-tramel/slop-guard --sparse .claude-plugin plugins
claude plugin install slop-guard@slop-guard --config response_checks=false
```

This installs the MCP tools without checking Claude's responses. To opt in at install time, set the declared plugin option to true instead:

```bash
claude plugin install slop-guard@slop-guard --config response_checks=true
```

## Codex

Codex CLI 0.144.0 or newer is required for bundled response-hook support. Add only the Codex catalog and Slop-Guard plugin directory, then install:

```bash
codex plugin marketplace add eric-tramel/slop-guard \
  --sparse .agents/plugins \
  --sparse plugins/slop-guard
codex plugin add slop-guard@slop-guard
```

Codex does not run the bundled response hook until you open `/hooks`, review it, and trust it. That trust step is the opt-in. You can return to `/hooks` to disable it.

## Response-check behavior

The hook analyzes only the main agent's `Stop` event; it does not handle `SubagentStop`. Any finding is a report produced after response generation. The hook does not suppress, retract, or rewrite the answer, which may already be visible.

The shared launcher requires POSIX `/bin/sh`. Native Windows is not supported.

## Direct MCP fallback

If you only need the MCP tools, including with Slop-Guard 0.5.0, register the existing `uvx slop-guard` server directly instead of installing a plugin:

```bash
claude mcp add slop-guard -- uvx slop-guard
codex mcp add slop-guard -- uvx slop-guard
```

You can append `-c /path/to/config.jsonl` after `slop-guard` to load custom rules. Direct registration does not install the bundled response hook.

## Pin a release

For a fixed direct invocation, pin the package version:

```bash
uvx slop-guard==0.5.0
```

Use the release selector in this documentation site when you want the matching docs for that pinned version. Each published page also has a raw Markdown sibling at the same slug, such as `/docs/get-started.md`.

Use a release for stable automation. Use `dev (main)` when testing repository behavior before the next tag.
