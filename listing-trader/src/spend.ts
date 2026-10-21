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
`;

export const RESERVE_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtext($1))";
export const RESERVE_SUM_SQL =
  "SELECT COALESCE(SUM(usd), 0)::text AS total FROM spend_journal WHERE spent_on = $1::date AND status IN ('reserved', 'committed')";
export const RESERVE_UPSERT_SQL = `
INSERT INTO spend_journal (idempotency_key, usd, spent_on, status)
VALUES ($1, $2, $3::date, 'reserved')
ON CONFLICT (idempotency_key) DO UPDATE
SET usd = EXCLUDED.usd, spent_on = EXCLUDED.spent_on, status = 'reserved'
WHERE spend_journal.status = 'released'
`;
export const COMMIT_SQL = "UPDATE spend_journal SET status = 'committed' WHERE idempotency_key = $1 AND status = 'reserved'";
export const RELEASE_SQL = "UPDATE spend_journal SET status = 'released' WHERE idempotency_key = $1 AND status = 'reserved'";

export type SpendStatus = "reserved" | "committed" | "released";

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

export function utcDay(now = new Date()): string {
  return now.toISOString().slice(0, 10);
}

async function poolFor(databaseUrl: string) {
  const { default: pg } = await import("pg");
  const pool = new pg.Pool({ connectionString: databaseUrl });
  await pool.query(SPEND_SCHEMA);
  return pool;
}

export async function spentOnDay(databaseUrl: string, day: string): Promise<number> {
  const pool = await poolFor(databaseUrl);
  try {
    const result = await pool.query<{ total: string | null }>(RESERVE_SUM_SQL, [day]);
    const total = Number(result.rows[0]?.total ?? 0);
    return Number.isFinite(total) ? total : 0;
  } finally {
    await pool.end();
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
    await pool.end();
  }
}

export async function commitSpend(databaseUrl: string, idempotencyKey: string): Promise<void> {
  const pool = await poolFor(databaseUrl);
  try {
    await pool.query(COMMIT_SQL, [idempotencyKey]);
  } finally {
    await pool.end();
  }
}

export async function releaseSpend(databaseUrl: string, idempotencyKey: string): Promise<void> {
  const pool = await poolFor(databaseUrl);
  try {
    await pool.query(RELEASE_SQL, [idempotencyKey]);
  } finally {
    await pool.end();
  }
}
