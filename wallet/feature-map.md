# Feature map

Each row names a feature and the check that proves it. Add a row when a feature moves.

| Feature | Check |
| --- | --- |
| Dry-run listing route picks the better net quote | `npm test` in this directory. The executor and pricing tests cover it. |
| Live send is screened, simulated, reserved, and policy checked | `npm test`. The send-path and security-review tests cover it. |
| Withdraw needs the admin token, the allowlist, and the per-call cap | `npm test`. The custody and controls tests cover it. |
| Resolver returns a hit only for a listed, liquid token | `npm test`. The match and refresh tests cover it. |
| No file grows past the agent budget | `node scripts/check-file-size.mjs` |
| Layers keep their import rules | `node scripts/check-boundaries.mjs` |
