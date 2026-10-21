import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import test from "node:test";

function repoRoot(start: string): string {
  let dir = start;
  for (let hop = 0; hop < 6; hop += 1) {
    if (existsSync(path.join(dir, "pyproject.toml"))) return dir;
    dir = path.dirname(dir);
  }
  throw new Error("repo root not found");
}

function files(dir: string, suffix: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) out.push(...files(full, suffix));
    else if (name.endsWith(suffix)) out.push(full);
  }
  return out;
}

test("the rocket package does not import the wallet", () => {
  const root = repoRoot(import.meta.dirname);
  const hits: string[] = [];
  for (const file of files(path.join(root, "rocket"), ".py")) {
    const text = readFileSync(file, "utf8");
    if (text.includes("listing_trader") || text.includes("from wallet") || text.includes("import wallet")) hits.push(file);
  }
  for (const file of files(path.join(root, "wallet", "src"), ".ts")) {
    const text = readFileSync(file, "utf8");
    if (text.includes("from \"../rocket") || text.includes("from 'rocket")) hits.push(file);
  }
  assert.deepEqual(hits, []);
});
