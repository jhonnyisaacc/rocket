// AbortSignal.timeout uses an unref'd timer on Node 22, so a process whose only
// pending work is that timer can exit before it fires. Keep a ref'd timer instead.
export function timeoutSignal(ms: number): AbortSignal {
  const controller = new AbortController();
  setTimeout(() => controller.abort(new Error(`timeout after ${ms}ms`)), Math.max(0, ms));
  return controller.signal;
}

export function anySignal(signals: readonly AbortSignal[]): AbortSignal {
  const controller = new AbortController();
  for (const signal of signals) {
    if (signal.aborted) {
      controller.abort(signal.reason);
      return controller.signal;
    }
    signal.addEventListener("abort", () => controller.abort(signal.reason), { once: true });
  }
  return controller.signal;
}
