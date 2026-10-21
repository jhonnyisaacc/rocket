export const SPEND_SCHEMA = `
CREATE TABLE IF NOT EXISTS spend_journal (
  idempotency_key text PRIMARY KEY,
  usd double precision NOT NULL,
  spent_on date NOT NULL
);
`;

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
    const result = await pool.query<{ total: string | null }>("SELECT SUM(usd)::text AS total FROM spend_journal WHERE spent_on = $1", [day]);
    const total = Number(result.rows[0]?.total ?? 0);
    return Number.isFinite(total) ? total : 0;
  } finally {
    await pool.end();
  }
}

export async function recordSpend(databaseUrl: string, idempotencyKey: string, usd: number, day = utcDay()): Promise<"inserted" | "exists"> {
  const pool = await poolFor(databaseUrl);
  try {
    const result = await pool.query(
      "INSERT INTO spend_journal (idempotency_key, usd, spent_on) VALUES ($1, $2, $3) ON CONFLICT (idempotency_key) DO NOTHING",
      [idempotencyKey, usd, day],
    );
    return result.rowCount === 1 ? "inserted" : "exists";
  } finally {
    await pool.end();
  }
}

export async function releaseSpend(databaseUrl: string, idempotencyKey: string): Promise<void> {
  const pool = await poolFor(databaseUrl);
  try {
    await pool.query("DELETE FROM spend_journal WHERE idempotency_key = $1", [idempotencyKey]);
  } finally {
    await pool.end();
  }
}
