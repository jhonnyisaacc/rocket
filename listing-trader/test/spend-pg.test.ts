import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import test from "node:test";
import pg from "pg";
import type { TxOutcome, TxRecord } from "../src/domain.js";
import { closeSpendPools, commitSpend, reconcileReserved, recordSpend, recordTx, releaseSpend } from "../src/spend.js";

const url = process.env.TEST_DATABASE_URL;

function tx(txHash: string, outcome: TxOutcome): TxRecord {
  return { chainKey: "base", txHash, from: "0xowner", to: "0xrouter", value: "0", outcome };
}

test("spend journal records tx hashes and boot reconciliation settles aged reservations", { skip: !url }, async () => {
  const databaseUrl = url as string;
  const run = randomUUID();
  const key = (name: string) => `${run}:${name}`;
  const day = "2026-10-21";
  const client = new pg.Client({ connectionString: databaseUrl });
  await client.connect();
  try {
    for (const name of ["landed", "dead", "unknown", "nohash", "fresh", "replaced"]) {
      assert.equal(await recordSpend(databaseUrl, key(name), 1, day), "reserved");
    }
    assert.equal(await recordSpend(databaseUrl, key("landed"), 1, day), "exists");
    await recordTx(databaseUrl, key("landed"), tx(`${run}:a`, "pending"));
    await recordTx(databaseUrl, key("dead"), tx(`${run}:b`, "pending"));
    await recordTx(databaseUrl, key("unknown"), tx(`${run}:c`, "pending"));
    await recordTx(databaseUrl, key("fresh"), tx(`${run}:d`, "pending"));
    await recordTx(databaseUrl, key("replaced"), tx(`${run}:e1`, "pending"));
    await recordTx(databaseUrl, key("replaced"), tx(`${run}:e2`, "pending"));
    await recordTx(databaseUrl, key("replaced"), tx(`${run}:e1`, "expired"));
    const replaced = await client.query("SELECT tx_hash, outcome FROM spend_journal WHERE idempotency_key = $1", [key("replaced")]);
    assert.deepEqual(replaced.rows[0], { tx_hash: `${run}:e2`, outcome: "pending" });
    const audit = await client.query("SELECT outcome FROM signed_tx WHERE tx_hash = $1", [`${run}:e1`]);
    assert.equal(audit.rows[0]?.outcome, "expired");
    await client.query(
      "INSERT INTO spend_journal (idempotency_key, usd, spent_on, status, reserved_at) VALUES ($1, 1, $2::date, 'reserved', NULL)",
      [key("legacy"), day],
    );
    await client.query("UPDATE spend_journal SET reserved_at = now() - interval '1 hour' WHERE idempotency_key = ANY($1)", [
      ["landed", "dead", "unknown", "nohash", "replaced"].map(key),
    ]);
    const outcomes: Record<string, TxOutcome> = { [`${run}:a`]: "landed", [`${run}:b`]: "expired", [`${run}:c`]: "pending", [`${run}:e2`]: "landed" };
    const seen: string[] = [];
    await reconcileReserved(databaseUrl, 10, async (_chain, hash) => outcomes[hash] ?? null, (entry) => {
      if (entry.idempotencyKey.startsWith(run)) seen.push(entry.idempotencyKey);
    });
    const rows = await client.query<{ idempotency_key: string; status: string }>("SELECT idempotency_key, status FROM spend_journal WHERE idempotency_key LIKE $1", [`${run}:%`]);
    const status = Object.fromEntries(rows.rows.map((row) => [row.idempotency_key.slice(run.length + 1), row.status]));
    assert.deepEqual(status, {
      landed: "committed",
      dead: "released",
      unknown: "reserved",
      nohash: "released",
      fresh: "reserved",
      replaced: "committed",
      legacy: "reserved",
    });
    assert.equal(seen.includes(key("fresh")), false);
    assert.equal(await recordSpend(databaseUrl, key("dead"), 1, day), "reserved");
    const rereserved = await client.query("SELECT tx_hash, reserved_at IS NOT NULL AS stamped FROM spend_journal WHERE idempotency_key = $1", [key("dead")]);
    assert.deepEqual(rereserved.rows[0], { tx_hash: null, stamped: true });
    await commitSpend(databaseUrl, key("dead"));
    await releaseSpend(databaseUrl, key("dead"));
    const settled = await client.query("SELECT status FROM spend_journal WHERE idempotency_key = $1", [key("dead")]);
    assert.equal(settled.rows[0]?.status, "committed");
  } finally {
    await client.query("DELETE FROM spend_journal WHERE idempotency_key LIKE $1", [`${run}:%`]);
    await client.query("DELETE FROM signed_tx WHERE tx_hash LIKE $1", [`${run}:%`]);
    await client.end();
    await closeSpendPools();
  }
});
