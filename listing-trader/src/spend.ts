import type { TxOutcome, TxRecord } from "./domain.js";

export const SPEND_SCHEMA = `
CREATE TABLE IF NOT EXISTS spend_journal (
  idempotency_key text PRIMARY KEY,
  usd double precision NOT NULL,
  spent_on date NOT NULL,
  status text NOT NULL DEFAULT 'committed'
);
ALTER TABLE spend_journal ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'committed';
DO $$ BEGIN
  ALTER TABLE spend_journal ADD CONSTRAINT spend_journal_status_check CHECK (status IN ('reserved', 'committed', 'released'));
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;
ALTER TABLE spend_journal ADD COLUMN IF NOT EXISTS reserved_at timestamptz;
ALTER TABLE spend_journal ADD COLUMN IF NOT EXISTS tx_hash text;
ALTER TABLE spend_journal ADD COLUMN IF NOT EXISTS chain_key text;
ALTER TABLE spend_journal ADD COLUMN IF NOT EXISTS outcome text;
ALTER TABLE spend_journal ADD COLUMN IF NOT EXISTS note text;
CREATE TABLE IF NOT EXISTS signed_tx (
  tx_hash text PRIMARY KEY,
  idempotency_key text,
  chain_key text NOT NULL,
  from_address text NOT NULL,
  to_address text NOT NULL,
  value text NOT NULL,
  outcome text NOT NULL,
  note text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
`;

export const RESERVE_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtext($1))";
export const RESERVE_SUM_SQL =
  "SELECT COALESCE(SUM(usd), 0)::text AS total FROM spend_journal WHERE spent_on = $1::date AND status IN ('reserved', 'committed')";
export const RESERVE_UPSERT_SQL = `
INSERT INTO spend_journal (idempotency_key, usd, spent_on, status, reserved_at)
VALUES ($1, $2, $3::date, 'reserved', now())
ON CONFLICT (idempotency_key) DO UPDATE
SET usd = EXCLUDED.usd, spent_on = EXCLUDED.spent_on, status = 'reserved', reserved_at = now(),
  tx_hash = NULL, chain_key = NULL, outcome = NULL, note = NULL
WHERE spend_journal.status = 'released'
`;
export const SIGNED_TX_SQL = `
INSERT INTO signed_tx (tx_hash, idempotency_key, chain_key, from_address, to_address, value, outcome, note)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (tx_hash) DO UPDATE SET outcome = EXCLUDED.outcome, note = EXCLUDED.note, updated_at = now()
`;
export const SPEND_TX_SQL = `
UPDATE spend_journal SET tx_hash = $2, chain_key = $3, outcome = $4, note = $5
WHERE idempotency_key = $1 AND (tx_hash IS NULL OR tx_hash = $2 OR $4 IN ('pending', 'landed'))
`;
export const RESERVED_SQL = `
SELECT idempotency_key, tx_hash, chain_key, reserved_at IS NULL AS legacy FROM spend_journal
WHERE status = 'reserved' AND (reserved_at IS NULL OR reserved_at < now() - make_interval(mins => $1::int))
`;
export const COMMIT_SQL = "UPDATE spend_journal SET status = 'committed' WHERE idempotency_key = $1 AND status = 'reserved'";
export const RELEASE_SQL = "UPDATE spend_journal SET status = 'released' WHERE idempotency_key = $1 AND status = 'reserved'";
export const CONTROL_SCHEMA = `
CREATE TABLE IF NOT EXISTS control_flags (
  name text PRIMARY KEY,
  enabled boolean NOT NULL
);
`;
export const KILL_SWITCH_SQL = "SELECT enabled FROM control_flags WHERE name = 'kill_switch'";

export type SpendStatus = "reserved" | "committed" | "released";

export type ReservedRow = { idempotencyKey: string; txHash: string | null; chainKey: string | null; legacy: boolean };

export function reconcileDecision(row: ReservedRow, outcome: TxOutcome | null): "commit" | "release" | "keep" {
  if (row.legacy) return "keep";
  if (!row.txHash) return "release";
  if (outcome === "landed") return "commit";
  if (outcome === "reverted" || outcome === "expired") return "release";
  return "keep";
}

export function reserveDecision(input: {
  existing: SpendStatus | null;
  spent: number;
  usd: number;
  cap: number;
}): "reserved" | "exists" | "cap" {
  if (input.existing === "reserved" || input.existing === "committed") return "exists";
  if (!(input.usd > 0) || input.spent + input.usd > input.cap) return "cap";
  return "reserved";
}

export function spendDay(now = new Date(), timeZone = "UTC"): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

export function utcDay(now = new Date()): string {
  return spendDay(now, "UTC");
}

export function killSwitchOn(envOn: boolean, rowEnabled: boolean | null): boolean {
  return envOn || rowEnabled === true;
}

export function createMemoryJournal() {
  const rows = new Map<string, { usd: number; day: string; status: SpendStatus }>();
  let tail = Promise.resolve();
  const lock = <T>(fn: () => T): Promise<T> => {
    const run = tail.then(fn, fn);
    tail = run.then(
      () => undefined,
      () => undefined,
    );
    return run;
  };
  return {
    reserve(key: string, usd: number, day: string, cap: number) {
      return lock(() => {
        const existing = rows.get(key)?.status ?? null;
        let spent = 0;
        for (const row of rows.values()) {
          if (row.day === day && (row.status === "reserved" || row.status === "committed")) spent += row.usd;
        }
        const decision = reserveDecision({ existing, spent, usd, cap });
        if (decision === "reserved") rows.set(key, { usd, day, status: "reserved" });
        return decision;
      });
    },
  };
}

const pools = new Map<string, import("pg").Pool>();
const ready = new Set<string>();

async function poolFor(databaseUrl: string) {
  const { default: pg } = await import("pg");
  let pool = pools.get(databaseUrl);
  if (!pool) {
    pool = new pg.Pool({ connectionString: databaseUrl, max: 4 });
    pools.set(databaseUrl, pool);
  }
  if (!ready.has(databaseUrl)) {
    await pool.query(SPEND_SCHEMA);
    await pool.query(CONTROL_SCHEMA);
    ready.add(databaseUrl);
  }
  return pool;
}

export async function spentOnDay(databaseUrl: string, day: string): Promise<number> {
  const pool = await poolFor(databaseUrl);
  try {
    const result = await pool.query<{ total: string | null }>(RESERVE_SUM_SQL, [day]);
    const total = Number(result.rows[0]?.total ?? 0);
    return Number.isFinite(total) ? total : 0;
  } catch (error) {
    ready.delete(databaseUrl);
    throw error;
  }
}

export async function recordSpend(
  databaseUrl: string,
  idempotencyKey: string,
  usd: number,
  day = utcDay(),
  capUsd = Number.POSITIVE_INFINITY,
): Promise<"reserved" | "exists" | "cap"> {
  const pool = await poolFor(databaseUrl);
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query(RESERVE_LOCK_SQL, [day]);
    const existing = await client.query<{ status: SpendStatus }>("SELECT status FROM spend_journal WHERE idempotency_key = $1", [idempotencyKey]);
    const status = existing.rows[0]?.status ?? null;
    const sum = await client.query<{ total: string | null }>(RESERVE_SUM_SQL, [day]);
    const spent = Number(sum.rows[0]?.total ?? 0);
    const decision = reserveDecision({ existing: status, spent: Number.isFinite(spent) ? spent : 0, usd, cap: capUsd });
    if (decision !== "reserved") {
      await client.query("ROLLBACK");
      return decision;
    }
    await client.query(RESERVE_UPSERT_SQL, [idempotencyKey, usd, day]);
    await client.query("COMMIT");
    return "reserved";
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}

export async function commitSpend(databaseUrl: string, idempotencyKey: string): Promise<void> {
  const pool = await poolFor(databaseUrl);
  await pool.query(COMMIT_SQL, [idempotencyKey]);
}

export async function releaseSpend(databaseUrl: string, idempotencyKey: string): Promise<void> {
  const pool = await poolFor(databaseUrl);
  await pool.query(RELEASE_SQL, [idempotencyKey]);
}

export async function readKillSwitch(databaseUrl: string): Promise<boolean> {
  const pool = await poolFor(databaseUrl);
  const result = await pool.query<{ enabled: boolean }>(KILL_SWITCH_SQL);
  return result.rows[0]?.enabled === true;
}

export async function recordTx(databaseUrl: string, idempotencyKey: string | null, tx: TxRecord): Promise<void> {
  const pool = await poolFor(databaseUrl);
  await pool.query(SIGNED_TX_SQL, [tx.txHash, idempotencyKey, tx.chainKey, tx.from, tx.to, tx.value, tx.outcome, tx.note ?? null]);
  if (idempotencyKey) await pool.query(SPEND_TX_SQL, [idempotencyKey, tx.txHash, tx.chainKey, tx.outcome, tx.note ?? null]);
}

export async function reconcileReserved(
  databaseUrl: string,
  olderThanMinutes: number,
  lookup: (chainKey: string, txHash: string) => Promise<TxOutcome | null>,
  log: (entry: { idempotencyKey: string; txHash: string | null; action: "commit" | "release" | "keep"; outcome: TxOutcome | null }) => void,
): Promise<number> {
  const pool = await poolFor(databaseUrl);
  const result = await pool.query<{ idempotency_key: string; tx_hash: string | null; chain_key: string | null; legacy: boolean }>(RESERVED_SQL, [olderThanMinutes]);
  for (const raw of result.rows) {
    const row: ReservedRow = { idempotencyKey: raw.idempotency_key, txHash: raw.tx_hash, chainKey: raw.chain_key, legacy: raw.legacy };
    const outcome = row.txHash && row.chainKey ? await lookup(row.chainKey, row.txHash).catch(() => null) : null;
    const action = reconcileDecision(row, outcome);
    if (action === "commit") await pool.query(COMMIT_SQL, [row.idempotencyKey]);
    if (action === "release") await pool.query(RELEASE_SQL, [row.idempotencyKey]);
    log({ idempotencyKey: row.idempotencyKey, txHash: row.txHash, action, outcome });
  }
  return result.rows.length;
}

export async function closeSpendPools(): Promise<void> {
  const open = [...pools.values()];
  pools.clear();
  ready.clear();
  await Promise.all(open.map((pool) => pool.end()));
}
