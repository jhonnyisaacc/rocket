import type { SendResult } from "../src/domain.js";

export function landedSend(): SendResult {
  return {
    venue: "chain",
    outcome: "landed",
    txs: [{ chainKey: "solana", txHash: "sig", from: "owner", to: "router", value: "0", outcome: "landed" }],
    held: null,
    shortfall: false,
  };
}
