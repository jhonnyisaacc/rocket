# Listing trader

Two Node 22 services for listing alerts. They live beside the Rocket CLI and are not imported by it. Rocket stays `READ_ONLY_RESEARCH_ONLY_HUMAN_GATED`. These processes do not score research and they do not admit an experiment.

Dry-run is the default. A buy is sent only when `LISTING_TRADER_LIVE` is the exact string `true`.

| Piece | Role |
| --- | --- |
| Resolver | Watchlist, pair map, name match |
| Executor | Route, quote, sign, and the copy-trading `POST /execute` entry |

Read [the architecture](docs/architecture.md), [the runbook](docs/runbook.md), [the threat model](docs/threat-model.md), and [how to deploy](docs/deploy.md).

```bash
cd listing-trader
npm ci
npm test
npm run create-wallet
npm run start:resolver
npm run start:executor
```

`npm test` compiles and runs the unit tests. It does not call an exchange.
