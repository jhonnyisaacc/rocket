import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path: string): string {
  return readFileSync(new URL(`../../${path}`, import.meta.url), "utf8");
}

test("every host manifest parses and names the rocket plugin", () => {
  for (const path of [".grok-plugin/plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".muse-plugin/plugin.json"]) {
    const parsed = JSON.parse(read(path)) as { name: string };
    assert.equal(parsed.name, "rocket", path);
  }
});

test("the Muse manifest declares the three skills and the MCP server", () => {
  const parsed = JSON.parse(read(".muse-plugin/plugin.json")) as { capabilities: { skills: { id: string }[]; mcpServers: { id: string; command: string[] }[] } };
  assert.deepEqual(parsed.capabilities.skills.map((skill) => skill.id), ["rocket-get-started", "rocket-pay-and-swap", "rocket-x402-services"]);
  assert.equal(parsed.capabilities.mcpServers[0].id, "rocket");
  assert.ok(parsed.capabilities.mcpServers[0].command.join(" ").includes("mcp-server"));
});

test("the dot-directory agents carry the same non-negotiable rules", () => {
  const files = [".claude/agents/rocket-wallet.md", "agents/claude/rocket-wallet.md", "agents/muse/rocket-wallet.md", ".codex/agents/rocket-wallet.toml", "agents/codex/rocket-wallet.toml"];
  for (const file of files) {
    const text = read(file);
    assert.ok(text.includes("wallet_status"), file);
    assert.ok(text.toLowerCase().includes("seed phrase"), file);
    assert.ok(text.includes("pending_approval"), file);
  }
});
