import { z } from "zod";

export const supportTierSchema = z.enum(["live", "dry_run", "disabled"]);
export type SupportTier = z.infer<typeof supportTierSchema>;

const DEFAULT_SUPPORT: Readonly<Record<string, SupportTier>> = { monad: "disabled", zksync: "dry_run" };

export function defaultSupportTier(chainKey: string): SupportTier {
  return DEFAULT_SUPPORT[chainKey] ?? "live";
}

export function supportByChain(chainKeys: Iterable<string>, raw: string | undefined): Record<string, SupportTier> {
  const out: Record<string, SupportTier> = {};
  for (const key of chainKeys) out[key] = defaultSupportTier(key);
  if (!raw) return out;
  for (const part of raw.split(",").map((item) => item.trim()).filter(Boolean)) {
    const [key, tier] = part.split(":");
    const parsed = supportTierSchema.safeParse(tier);
    if (!key || !parsed.success) throw new Error("SUPPORT_TIERS entries look like chain:live, chain:dry_run, or chain:disabled");
    out[key] = parsed.data;
  }
  return out;
}

export function supportTierFor(support: Readonly<Record<string, SupportTier>>, chainKey: string): SupportTier {
  return support[chainKey] ?? defaultSupportTier(chainKey);
}

export function liveTierBlocked(mode: "live" | "dry_run", tierFor: ((chainKey: string) => SupportTier) | undefined, chainKey: string): boolean {
  return mode === "live" && tierFor !== undefined && tierFor(chainKey) !== "live";
}
