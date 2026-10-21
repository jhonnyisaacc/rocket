import { BroadcastError } from "./executor.js";

const NONCE_REJECTED = /nonce too low|nonce has already been used|replacement transaction underpriced|transaction underpriced|nonce_expired|invalid nonce/i;

export function isNonceRejection(message: string): boolean {
  return NONCE_REJECTED.test(message);
}

type Slot = { next: number | null; tail: Promise<unknown> };

export type NonceManager = {
  use<T>(chainId: number, address: string, readPending: () => Promise<number>, send: (nonce: number) => Promise<T>): Promise<T>;
};

export function createNonceManager(): NonceManager {
  const slots = new Map<string, Slot>();
  return {
    use(chainId, address, readPending, send) {
      const key = `${chainId}:${address.toLowerCase()}`;
      const slot = slots.get(key) ?? { next: null, tail: Promise.resolve() };
      slots.set(key, slot);
      const run = slot.tail.then(async () => {
        if (slot.next === null) slot.next = await readPending();
        const nonce = slot.next;
        try {
          const out = await send(nonce);
          slot.next = nonce + 1;
          return out;
        } catch (error) {
          if (error instanceof BroadcastError && isNonceRejection(error.message)) slot.next = null;
          else if (error instanceof BroadcastError && error.broadcast) slot.next = nonce + 1;
          throw error;
        }
      });
      slot.tail = run.catch(() => undefined);
      return run;
    },
  };
}

export const evmNonces = createNonceManager();
