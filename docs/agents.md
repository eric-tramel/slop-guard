---
icon: lucide/bot
---

# Agents

Both supported clients use the same MCP command:

```bash
uvx slop-guard
```

That starts the local MCP server. It processes text locally and returns structured diagnostics for agents drafting docs, release notes, or status updates.

The MCP surface is small on purpose. Agents can call `check_slop` when they already have text in memory, or `check_slop_file` when they need to inspect a file on disk. Both tools return structured JSON, so the client can point at exact spans and feed the advice back into the rewrite loop.

Passages with 50 or more words also return `review_requirements`. The server lists semantic criteria for the invoking writing agent. The agent judges each criterion against the full passage, rewrites failed sections from their intended meaning, then runs the tool again. A numeric score covers the deterministic stage.

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

## Pin a release

If an automation or team workflow needs a fixed package version, pin it in the command arguments:

```bash
uvx slop-guard==0.5.0
```

Use the release selector in this documentation site when you want the matching docs for that pinned version.

Every published docs page also exposes a raw Markdown sibling at the same slug. For example, the rendered `get-started` page lives alongside `/docs/get-started.md`, which makes scripted crawling easier for agents and automation.

If you are deciding between a release and `dev (main)`, use a release for stable automation and use `dev (main)` when you are testing current repository behavior before the next tag ships.
