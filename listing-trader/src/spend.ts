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
export const CONTROL_SCHEMA = `
CREATE TABLE IF NOT EXISTS control_flags (
  name text PRIMARY KEY,
  enabled boolean NOT NULL
);
`;
export const KILL_SWITCH_SQL = "SELECT enabled FROM control_flags WHERE name = 'kill_switch'";

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
