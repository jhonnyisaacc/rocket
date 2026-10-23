# Wallet

Secure, multichain agentic wallet. EVM L1 and L2 chains plus Solana. Dry-run is the default. Live signing goes through Turnkey only. The local keystore never signs live.

## Map

- `src/domain.ts` holds the shared types. `src/chains.ts` holds the chain table. Neither imports a service.
- `src/config/` loads and guards config. `src/config.ts` is a barrel.
- `src/aggregators/` races and firms quotes. `src/aggregators.ts` is a barrel.
- `src/broadcast/` sends EVM, Solana, and Hypercore transactions. `src/broadcast.ts` is a barrel plus the route orchestrator.
- `src/executor/` holds withdraw and quote planning. `src/executor.ts` holds the execute state machine.
- `src/executor-server/` holds the chain balance reader. `src/resolver-server.ts` and `src/executor-server.ts` are the only HTTP entry points.
- `src/signing-policy.ts` is the last check before any signature. A change here is a security change.

## Rules an agent cannot infer

- Keep every file at or under about 5,000 tokens. Split by feature. Keep the old import path as a barrel.
- Run `npm run check` before a PR. It runs the file-size ratchet, the import boundaries, the build, and the tests.
- Never ask a user or an agent for a seed phrase or a private key. Never print one.
- Amounts cross boundaries in the smallest unit. A decimal string is a display value only.
- A live send needs screening, simulation, the spend reservation, and the signing policy. Do not add a path that skips one.
- The Rocket Python package never imports this tree. The wall test enforces it.

## Verify

`npm run check` in this directory. See `feature-map.md` for what each feature check proves.
