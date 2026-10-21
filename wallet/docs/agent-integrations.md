# Rocket on agent hosts

One wallet serves three hosts. The MCP server and the skills stay the same. Only the manifest differs.

| Host | Manifest | Agent definition |
| --- | --- | --- |
| Grok | `.grok-plugin/plugin.json` | Host-managed. Skills under `skills/` |
| Claude | `.claude-plugin/plugin.json` | `agents/claude/rocket-wallet.md` |
| Codex | `.codex-plugin/plugin.json` | `agents/codex/rocket-wallet.toml` |

## Shared setup

Build the wallet. Start the resolver and the executor in dry-run. The MCP entry in `.mcp.json` starts `dist/src/mcp-server.js` over stdio.

Set `EXECUTOR_URL` and `RESOLVER_URL` for the MCP process. Set `EXECUTOR_AUTH_TOKEN` and `RESOLVER_AUTH_TOKEN` to the matching service tokens. The two tokens differ by design. Set `WALLET_APPROVAL_MODE` only to change the human step. The default is `always_approve`.

## Claude

Install this directory as a Claude plugin, or copy `agents/claude/rocket-wallet.md` into a project's `.claude/agents/`. The plugin reads the root `.mcp.json` and the root `skills/` directory. The subagent definition restricts itself to shell and read tools. All money movement still goes through the MCP tools and the executor gates.

## Codex

Install this directory as a Codex plugin, or copy `agents/codex/rocket-wallet.toml` into `.codex/agents/` at the project or user level. The plugin manifest points Codex at `./skills/` and `./.mcp.json`. The agent definition carries the same operating rules as the Claude definition. Keep both files in step when the rules change.

## Security

No host integration adds a money path. Every host reaches the same executor routes. A live listing still passes screening, simulation, the spend reservation, and the Turnkey signing policy. Under `iframe` or `always_approve`, the MCP tool returns `pending_approval` and sends nothing. No integration asks for a seed phrase or a key.
