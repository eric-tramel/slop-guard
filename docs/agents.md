---
icon: lucide/bot
---

# Agents

Both supported clients use the same MCP command:

```bash
uvx slop-guard
```

That starts the local MCP server without any API calls or model-side judging. The tools return structured diagnostics that agents can use while they draft docs, release notes, or status updates.

The MCP surface is small on purpose. Agents can call `check_slop` when they already have text in memory, or `check_slop_file` when they need to inspect a file on disk. Both tools return structured JSON, so the client can point at exact spans and feed the advice back into the rewrite loop.

## Codex

Register the server with Codex by pointing `mcp add` at `uvx slop-guard`, or add it to `~/.codex/config.toml`:

```toml
[mcp_servers.slop-guard]
command = "uvx"
args = ["slop-guard"]
```

## Claude Code

Register the server with Claude Code by pointing `mcp add` at `uvx slop-guard`, or add it to `.mcp.json`:

```json
{
  "mcpServers": {
    "slop-guard": {
      "command": "uvx",
      "args": ["slop-guard"]
    }
  }
}
```

## Choose a rule preset

The MCP server reads the same `-c` flag from its launch arguments that the CLI does. The default rule set is the `ai_slop` preset; pass `-c` with the bundled `writing_quality.jsonl` to opt into the opinionated style checks. Configure two MCP entries when you want both presets available to the agent.

Resolve the bundled writing-quality path and copy it somewhere stable:

```bash
python -c 'from importlib.resources import files; print(files("slop_guard.rules").joinpath("assets/writing_quality.jsonl").read_text())' > ~/.config/slop-guard/writing_quality.jsonl
```

Codex `~/.codex/config.toml`:

```toml
[mcp_servers.slop-guard]
command = "uvx"
args = ["slop-guard"]

[mcp_servers.slop-guard-writing-quality]
command = "uvx"
args = ["slop-guard", "-c", "/Users/you/.config/slop-guard/writing_quality.jsonl"]
```

Claude Code `.mcp.json`:

```json
{
  "mcpServers": {
    "slop-guard": {
      "command": "uvx",
      "args": ["slop-guard"]
    },
    "slop-guard-writing-quality": {
      "command": "uvx",
      "args": ["slop-guard", "-c", "/Users/you/.config/slop-guard/writing_quality.jsonl"]
    }
  }
}
```

Each violation the MCP tool returns carries a `category` field (`"ai_slop"` or `"writing_quality"`) that matches the preset that registered the rule, and `category_counts` aggregates violations per category.

## Pin a release

If an automation or team workflow needs a fixed package version, pin it in the command arguments:

```bash
uvx slop-guard==0.4.1
```

Use the release selector in this documentation site when you want the matching docs for that pinned version.

Every published docs page also exposes a raw Markdown sibling at the same slug. For example, the rendered `get-started` page lives alongside `/docs/get-started.md`, which makes scripted crawling easier for agents and automation.

If you are deciding between a release and `dev (main)`, use a release for stable automation and use `dev (main)` when you are testing current repository behavior before the next tag ships.
