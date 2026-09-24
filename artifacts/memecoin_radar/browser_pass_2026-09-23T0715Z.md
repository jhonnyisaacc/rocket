# Browser pass — 2026-09-23T07:15Z

NO_EDGE_VALIDATED. Human-gated. Read-only. Identification ≠ entry.
Browser and X are evidence sources, not execution.
Every result keeps edge=NO_EDGE_VALIDATED and execution_enabled=false.

Visual pass: cloud browser, roughly 2026-09-23T06:51Z through 2026-09-23T07:08Z.
API fallback retrieved_at: 2026-09-23T07:15:27Z.
No login, no wallet, no API key. Market-cap figures below are advertised labels from the response, not liquidity and not a buy.

## What the browser showed

### pump.fun

- `https://pump.fun/explore` — public board. Visible tabs included Movers, New, Custom pairs, Charities, Market cap, Oldest, Last trade. Filter controls seen were market-cap and 24h volume sliders. No control labeled graduated, completed, or bonded-off-curve.
- Cards showed a display name, a ticker, and a market-cap label. The mint was not printed on the card.
- `https://pump.fun/advanced` final URL: `https://trade.padre.gg/sign-in?utm_source=pumpweb`. Login wall. Not used.
- A transcribed coin URL for a Movers card 404’d with “Coin not found.” That string is not an identity.
- A second transcribed address bar did not match the mint embedded for that display name in the page payload. That transcription is not an identity.

The explore document itself names `clientServerUrl` = `https://frontend-api-v3.pump.fun`. The page bundle’s route table includes `GET /coins` with query fields `limit`, `offset`, `sort`, `order`, `includeNsfw`, `creator`, `complete`, and `boostModes`. `complete=true` is the graduated / bonding-curve-complete flag in that API. This pass called that URL because the board did not show mints.

### fomo.family and pump.family

- `https://fomo.family/` — login modal: “Login or create an account to start trading.” No public mint and no window state.
- `https://fomo.family/feed` — 404.
- `https://pump.family/` — public. The page script calls `fetch("/api/sales")` and `fetch("/api/health")`.
- `https://pump.family/explore` — public board. Filters visible: All, New, Closing soon, Migrated. Cards showed name, ticker, and market cap. Mints were not on the cards. Migrated is the off-curve / window-closed board. The homepage mint string read off the glass did not match the mint in `/api/sales` for the featured row, so the glass transcription is not used.

## Rows copied from the page JSON

Join key is the mint. Ticker is a label. `retrieved_at` for every row in this section is 2026-09-23T07:15:27Z.

Source URL for the pump rows:

`https://frontend-api-v3.pump.fun/coins?limit=20&offset=0&sort=created_timestamp&order=DESC&includeNsfw=false&complete=true`

`complete` was true on each of these. `chain_id` in the body was `solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp` (short mainnet id; ranked later as `solana:mainnet`). `real_quote` is raw quote lamports from the payload, not USD. Zero means the field did not report reserves. It is not proof of zero liquidity. `usd_market_cap` is not liquidity.

| Label | Mint | Pool (if present) | usd_market_cap | real_quote lamports | created_timestamp ms |
| --- | --- | --- | --- | --- | --- |
| MOUSE | `8MPLzMvudX7ehD8VjKSDDWCS9bAu1N6KK3Ubg5xypump` | `B973QMT3E6AFKJY8SSSsYib5MJzCBWa6xSNQs4zPAzgy` | 233754 | 0 | 1790147536000 |
| PUMP-KIN | `55CeV6Vc3TUgX3GJy7T9NJ6SfYT9XbR7ELyEboBrpump` | `6Pda9RPWu2ytXt9tgNbQzq3vqTsVrdwahtcB1xTLyZXa` | 19 | 0 | 1790147465000 |
| OURA | `HXTvN9TwdQe4ieZ6rPAc9uwnKw68Aem2NQwPxAuepump` | none | 8125599 | 85005359057 | 1790147457000 |
| FOMO | `A55bDitM2zxW2YdZNwzhGiAVUFEb88jShuY1CTSpump` | `8bp692QaijnkL6vd5C1xzKihH6ZKEvWTSEbXnDErX8aw` | 603997 | 85005359057 | 1790147299000 |

Eight rows were returned; four are listed. The other four from that same response were Wojak, Pan, STOCKCAT, and JEANSEAL. They are not repeated here so this file stays a sample of what was visible in the JSON, not a dump.

Source URL for the pump.family rows: `https://pump.family/api/sales` (127 sales in the body, `solUsd` about 118.95). Phase `migrated` is the closed FOMO window that has left the curve. Six migrated rows were in the body:

| Label | Mint | Pool | phase | windowEnd unix | marketCap field |
| --- | --- | --- | --- | --- | --- |
| FAMILY | `FvMLDEUDKUr9C34e8Nynz5Aqfdk34a2RBKQxygLpfomo` | `FdYPSUq2Zrw9vJXkA8uZFVNhNcCvUUuAcSWWVk6MZZhU` | migrated | null | 460.27 |
| PFCAT | `3DdbP1uddSA8y846jLBcJhUi5ECYw6CQtCviJvbgfomo` | `A1C4ZhBwhsjaPZifov37aepf9cv2RvEs7Gqgj8HZgzGd` | migrated | 1789995266 | 12.48 |
| PFDOG | `4Ukipu6Dsshkwy3DGy8nSeJHi8FJQ68XYFNAg9B2fomo` | `7C6Yw8jvTrFpFcbcKdwV5MQUGYEbim6skJe14C6oFScw` | migrated | 1789995479 | 3.98 |
| CAT | `DRxWK1FU7ci4vjGhMZu4koQpVLtut4gpxSpxtr6bfomo` | `DeRkuRb91VJ771E86d6j1nNzyn5Q8ZUcATqH3QMtyGeX` | migrated | 1789996912 | 2.65 |
| THEO | `62Twqf8daa3c8iS2v75ua7eexJdXCtd6NPJmrTzdfomo` | `gmTxfNADWnUNRdsLaLrH4aVgPdzvKMxKPB6ftCcFWPY` | migrated | 1789997141 | 4.17 |
| FOMOPILL | `5SN9SH1w9oSqVmJkbtttUduoCR5iSKMn1MjDTuD4fomo` | `DiNsopKE3Xg5phNnJViHqCyCyhBVb4zQVoMFdZAe1gpS` | migrated | 1789998134 | 7.49 |

`marketCap` on this payload is not treated as `liquidity_usd`. Window-open rows are not part of the universe. `fomo.family` itself contributed no mint.

## Helius on this machine

`HELIUS_API_KEY` was absent in the environment that wrote this file. None of these mints were confirmed on-chain here. They are discovery rows only. They are not `WATCH`.
