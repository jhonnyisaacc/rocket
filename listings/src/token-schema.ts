import { z } from "zod";

const chainSchema = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("solana") }),
  z.object({ kind: z.literal("evm"), chainId: z.number().int().positive() }),
  z.object({ kind: z.literal("hypercore"), market: z.enum(["perp", "spot"]) }),
]);

const poolSchema = z
  .object({
    poolAddress: z.string(),
    dex: z.string(),
    chainKey: z.string(),
    baseSymbol: z.string(),
    baseAddress: z.string(),
    quoteSymbol: z.string(),
    quoteAddress: z.string(),
    liquidityUsd: z.number(),
    priceUsd: z.number().nullable(),
    baseDecimals: z.number().nullable(),
  })
  .passthrough();

const pairMapSchema = z.object({
  pools: z.array(poolSchema),
  top: poolSchema.nullable(),
});

const hyperliquidSchema = z.object({
  coin: z.string(),
  assetIndex: z.number().int(),
  market: z.enum(["perp", "spot"]),
  maxLeverage: z.number(),
});

export const tokenRecordSchema = z
  .object({
    id: z.string(),
    ticker: z.string(),
    names: z.array(z.string()),
    chainKey: z.string(),
    chain: chainSchema,
    contract: z.string(),
    decimals: z.number().nullable(),
    pairMap: pairMapSchema,
    hyperliquid: hyperliquidSchema.nullable(),
    refreshedAt: z.string(),
  })
  .passthrough();
