export type HttpClass = "ok" | "compliance" | "rate" | "error";

const COMPLIANCE = /sanction|ofac|compliance|restricted jurisdiction|geoblock|denied by policy/;

export function classifyHttp(status: number, body: string): HttpClass {
  if (status >= 200 && status < 300) return "ok";
  if (status === 451 || COMPLIANCE.test(body.toLowerCase())) return "compliance";
  if (status === 429) return "rate";
  return "error";
}

export function retryAfterAt(header: string | null, now: number): number | null {
  if (!header) return null;
  const trimmed = header.trim();
  if (/^\d+$/.test(trimmed)) return now + Number(trimmed) * 1000;
  const at = Date.parse(trimmed);
  return Number.isFinite(at) && at > now ? at : null;
}

type Row = { failures: number; openUntil: number; used: number; windowStart: number; compliance: boolean };

export class ProviderGuard {
  private readonly rows = new Map<string, Row>();

  constructor(
    private readonly options: {
      budget: number;
      windowMs: number;
      failureThreshold: number;
      openMs: number;
      now: () => number;
    },
  ) {}

  before(id: string): "allow" | "open" | "budget" {
    const row = this.row(id);
    const now = this.options.now();
    if (row.openUntil > now) return "open";
    if (now - row.windowStart >= this.options.windowMs) {
      row.windowStart = now;
      row.used = 0;
    }
    if (row.used >= this.options.budget) return "budget";
    row.used += 1;
    return "allow";
  }

  success(id: string): void {
    const row = this.row(id);
    row.failures = 0;
    row.compliance = false;
  }

  failure(id: string): void {
    const row = this.row(id);
    row.failures += 1;
    if (row.failures >= this.options.failureThreshold) row.openUntil = this.options.now() + this.options.openMs;
  }

  rateLimited(id: string, retryAt: number | null): void {
    this.failure(id);
    const row = this.row(id);
    if (retryAt !== null && retryAt > row.openUntil) row.openUntil = retryAt;
  }

  compliance(id: string): void {
    const row = this.row(id);
    row.compliance = true;
    row.openUntil = this.options.now() + this.options.openMs;
  }

  complianceOpen(id: string): boolean {
    return this.row(id).compliance && this.row(id).openUntil > this.options.now();
  }

  private row(id: string): Row {
    const existing = this.rows.get(id);
    if (existing) return existing;
    const created: Row = { failures: 0, openUntil: 0, used: 0, windowStart: this.options.now(), compliance: false };
    this.rows.set(id, created);
    return created;
  }
}
