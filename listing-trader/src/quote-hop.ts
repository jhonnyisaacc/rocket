import type { ChainRef } from "./domain.js";

export type QuoteHop = {
  sellAddress: string;
  buyAddress: string;
  sellAmount: string;
  chain: ChainRef;
};

const AMOUNT = /^[1-9][0-9]{0,77}$/;

export function validSellAmount(amount: string): boolean {
  return AMOUNT.test(amount);
}
