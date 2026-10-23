import type { HyperliquidMarket, TokenRecord } from "./domain.js";
import { WatchIndex } from "./match.js";
import { attachHyperliquid } from "./parsers.js";
import { tokenRecordSchema } from "./schemas.js";

export const TOKEN_SCHEMA = `
CREATE TABLE IF NOT EXISTS verified_tokens (
  id text PRIMARY KEY,
  ticker text NOT NULL,
  payload jsonb NOT NULL,
  refreshed_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS verified_tokens_ticker ON verified_tokens (ticker);
`;

export class MemoryWatchlist {
  readonly index = new WatchIndex();
  private tokens: TokenRecord[] = [];
  private markets: HyperliquidMarket[] = [];

  replace(tokens: readonly TokenRecord[]): void {
    this.tokens = tokens.slice();
    this.index.replace(this.tokens);
  }

  records(): readonly TokenRecord[] {
    return this.tokens;
  }

  setMarkets(markets: readonly HyperliquidMarket[]): void {
    this.markets = markets.slice();
  }

  upsert(token: TokenRecord): void {
    const linked = this.markets.length > 0 ? attachHyperliquid(token, this.markets) : token;
    const rest = this.tokens.filter((item) => item.id !== linked.id);
    this.replace([...rest, linked]);
  }
}

export async function hydrateFromPostgres(databaseUrl: string): Promise<TokenRecord[]> {
  const { default: pg } = await import("pg");
  const pool = new pg.Pool({ connectionString: databaseUrl });
  try {
    await pool.query(TOKEN_SCHEMA);
    const result = await pool.query<{ payload: TokenRecord }>("SELECT payload FROM verified_tokens");
    return parseTokenRecords(result.rows.map((row) => row.payload));
  } finally {
    await pool.end();
  }
}

export async function saveToPostgres(databaseUrl: string, tokens: readonly TokenRecord[]): Promise<void> {
  const { default: pg } = await import("pg");
  const pool = new pg.Pool({ connectionString: databaseUrl });
  const client = await pool.connect();
  try {
    await client.query(TOKEN_SCHEMA);
    await client.query("BEGIN");
    await client.query("DELETE FROM verified_tokens");
    for (const token of tokens) {
      await client.query("INSERT INTO verified_tokens (id, ticker, payload, refreshed_at) VALUES ($1, $2, $3, $4)", [
        token.id,
        token.ticker,
        JSON.stringify(token),
        token.refreshedAt,
      ]);
    }
    await client.query("COMMIT");
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
    await pool.end();
  }
}

export function parseTokenRecords(payloads: readonly unknown[]): TokenRecord[] {
  const out: TokenRecord[] = [];
  for (const payload of payloads) {
    const parsed = tokenRecordSchema.safeParse(payload);
    if (parsed.success) out.push(parsed.data as TokenRecord);
  }
  return out;
}
