## Solana Memecoin Dataset

A labeled snapshot dataset of early-stage Solana memecoins, plus the GMGN
collection scripts used to build it.

Collected continuously over ~20 days (2026-06-10 to 2026-06-30) by watching
freshly-graduated pump.fun tokens and the GMGN trending board. Each candidate
gets a **feature snapshot at detection time** (holder structure, smart-money
activity, contract safety, trading behavior, momentum trajectory), later
backfilled with the **real forward max return at 1h/6h/24h/3d** as a label.
Originally built to train an "early buy" ML model; the project has been
shelved and the data + collection scripts are released for research use.

> **This is a labeled snapshot dataset of ~44k early-stage Solana memecoin
> observations (June 2026), with 9.5M wallet-level trades, OHLCV candles, and
> wallet profiles. Each snapshot carries ~80 features captured at detection
> time and forward-looking max-return labels (1h/6h/24h/3d). Collection
> scripts (GMGN.ai only) are included.**

## Dataset overview

| File | Rows | Content |
|---|---|---|
| `data/tokens.parquet` | 44,460 | Main table: one snapshot per token per detection + forward-return labels |
| `data/trades-000..003.parquet` | 9,500,565 | Wallet-level trade log (wallet x token buy/sell, for graph construction) |
| `data/ohlcv.parquet` | 272,426 | 15-minute candles (within each label window, USD-denominated) |
| `data/sequences.parquet` | 506,628 | Fixed-length time-bucket sequences from launch to detection (20 buckets x 5 features, for LSTM use) |
| `data/wallets.parquet` | 11,817 | Wallet profiles: GMGN tags, win rate, PnL ratio, PageRank |
| `data/wallet_funding.parquet` | 15,493 | Wallet funding edges (who sent SOL to whom, for cluster detection) |

All addresses are public on-chain data. Quickstart:

```python
import pandas as pd

tokens = pd.read_parquet("data/tokens.parquet")
trades = pd.concat(pd.read_parquet(f"data/trades-{i:03d}.parquet") for i in range(4))

# e.g. fraction of tokens that 2x within 24h of detection
print(tokens["reaches_2x"].mean())          # ~0.11
# e.g. full buy/sell flow for one token
trades[trades.token_address == tokens.token_address.iloc[0]]
```

## `tokens.parquet` column reference

One row = one detection snapshot. `sample_id` is the primary key and is how
`sequences.parquet` joins back to this table.

**Identity & timing**
| Column | Description |
|---|---|
| `sample_id` | Snapshot primary key |
| `token_address` / `symbol` / `pool_address` | Token mint address / ticker / main pool address |
| `captured_at` | Snapshot time (UTC) |
| `time_since_launch_sec` | Seconds between launch and snapshot |
| `price_at_capture`, `market_cap_usd`, `liquidity_usd`, `volume_h24`, `number_markets` | Market state at snapshot time |

**Holder structure (GMGN)**
| Column | Description |
|---|---|
| `holder_count`, `top10_holder_pct` | Number of holders, top-10 address concentration |
| `dev_remaining_pct`, `rat_position_pct` | Dev's remaining holdings, "rat position" (insider pre-buy) share |
| `sniper_count`, `new_wallet_count`, `smart_money_count`, `smart_money_pct` | Sniper / new-wallet / smart-money counts |
| `cluster_count`, `cluster_max_pct`, `cluster_top3_pct`, `cluster_newest_days` | Holder-wallet "creation-time cluster" analysis (detects one entity behind many wallets) |
| `bundler_pct_holders`, `fresh_wallet_pct`, `insider_pct_holders`, `sniper_pct_holders`, `kol_pct_holders`, `smart_pct_holders` | Share of holders carrying each tagged wallet type |
| `only_buy_pct`, `low_freq_pct`, `fishing_pct`, `profitable_pct`, `pool_pct` | Behavioral holder shares (buy-only / low-frequency / phishing / currently profitable / pool) |

**Contract safety & socials**
| Column | Description |
|---|---|
| `mint_disabled`, `freeze_disabled` | Mint / freeze authority renounced |
| `lp_burned_pct`, `rug_probability` | LP burn percentage, honeypot/rug risk |
| `has_twitter`, `has_website`, `has_telegram` | Presence of social links |
| `is_boosted`, `boost_amount`, `boost_total` | DexScreener paid boosts |
| `tg_mention_count` | Telegram channel mention count (sparse coverage, ~5%) |

**Trading behavior (computed from the most recent 200 trades before the snapshot)**
| Column | Description |
|---|---|
| `price_change_1h`, `price_change_6h` | Momentum at snapshot time |
| `unique_buyers`, `unique_sellers`, `active_wallets` | Distinct buyers / sellers / active wallets |
| `buy_usd_1h`, `sell_usd_1h`, `net_flow_usd`, `trade_buy_sell_ratio` | Cash flow |
| `smart_buy_1h`, `kol_buy_1h`, `smart_concurrent_15m` | Smart-money / KOL buys, count of smart wallets buying within the same 15-minute window |
| `flipper_ratio`, `large_buy_streak`, `seller_loss_ratio` | Flip-in-flip-out ratio, consecutive large buys, share of sellers at a loss |
| `bundler_ratio`, `top_holder_ratio` | Share of active wallets that are bundler/top-holder wallets (insider control signal) |
| `insider_cluster_size`, `insider_holding_ratio`, `insider_net_usd` | Insider cluster size / holdings / net flow |
| `known_smart_count`, `known_insider_count` | Hits against the project's own smart-money/insider address book |
| `smart_ratio`, `early_smart_ratio`, `smart_earliness` | Smart-money share and how early they entered |
| `crew_cohesion` | Co-occurrence of buyer wallets across tokens (high = coordinated wash-trading crew, an **inverse** signal) |

**Momentum trajectory (launch-to-detection trade flow, split into early/mid/late segments)**
`buy_early`, `buy_late`, `buy_total`, `buy_last10`, `sell_late`,
`n_early`, `n_late`, `buyers_early`, `buyers_late`, `smart_entry_rec`
(the later/more recent smart money enters, the higher `smart_entry_rec`;
this feature group had the largest incremental predictive value in the
original project, ΔAUC +0.0095)

**Labels (backfilled after the fact — never use as features, this leaks)**
| Column | Description |
|---|---|
| `max_return_1h/6h/24h/3d` | Highest price within N of detection / price at detection (1.0 = no gain; 0.0 = went to zero) |
| `reaches_2x` | Whether it doubled within 24h |
| `runner_peak_x` | Peak multiple reached (for tokens that ran further) |
| `staged_exit_return` | Simulated staged-exit multiple (sell 50% at 2x, etc.) |
| `scalp_exit_return`, `close_return_1h`, `mdd_from_peak`, `time_to_peak_sec` | Scalp-exit simulation and path statistics |

## Other files

**`trades-*.parquet`** — `wallet, token_address, side(buy/sell), amount_usd, ts`.
Multiple rows per wallet/token pair are normal (partial fills). Can be used
to build a wallet<->token bipartite graph.
Warning: 9.5M rows; loading the full set needs 2GB+ RAM — prefer
`pyarrow.dataset` or DuckDB to filter before loading.

**`ohlcv.parquet`** — `token_address, ts, open, high, low, close, volume` (15m, USD).
Only covers each snapshot's label window (up to 3 days after detection), not
full history.
Warning: a small number of glitch candles remain (single-candle high spikes);
when computing returns, consider dropping rows where `high > close * 10`.

**`sequences.parquet`** — `sample_id, bucket(0-19), buy_usd, sell_usd, n_trades, n_smart_buy, n_buyers`.
Launch-to-detection window split into 20 equal time buckets, aggregated per
bucket. Joins to `tokens.parquet` on `sample_id`.

**`wallets.parquet`** — `address, wallet_type(smart_money/insider/normal), labels(GMGN tags, |-separated), win_rate, avg_pnl_ratio, trade_count_90d, avg_holding_hours, pagerank, cluster_id, ...`
`smart_money` definition: historical hit rate >=40% (n>=5) **and** realized
cash PnL >= 1.0 (USD sold >= USD bought).

**`wallet_funding.parquet`** — `wallet, funder, ts, amount_sol`. SOL funding
sources per wallet (this table comes from Helius RPC history; everything
else in the dataset comes from GMGN).

## Known biases & caveats (important)

1. **Survivorship bias**: the collection pipeline only sees tokens that
   survived long enough to be detected, so the sample's 2x rate (~11%) is
   somewhat higher than the true population rate.
2. **Labels are cleaned**: false positives caused by glitch candles
   (single-candle high/low > 50x) have been removed and re-labeled.
3. **Time range is only 20 days** (June 2026), a single market regime —
   extrapolate with caution.
4. `tg_mention_count` is shit, I'll remove it later.

## Collection scripts (`scripts/`, GMGN.ai only)

Self-contained and ready to run (SQLite output), no database server needed:

```bash
pip install -r requirements.txt

python scripts/collect.py --loop         # discovery + snapshot collection (every 10 min)
python scripts/label_returns.py --loop   # label backfill (every hour)
```

| File | Purpose |
|---|---|
| `gmgn_client.py` | Unified GMGN client: discovery (just-graduated / trending), token features, trades, market-cap candles |
| `collect.py` | Main collector: discover candidates -> feature snapshot + trades -> `collected.sqlite` |
| `label_returns.py` | Backfills `max_return_*` / `reaches_2x` from GMGN candles |

**Connectivity**: by default the scripts use `curl_cffi` to impersonate a
Chrome TLS fingerprint and hit the GMGN web API directly — this usually
works fine from residential IPs, but **datacenter IPs (AWS/GCP/VPS) get
blocked by Cloudflare**. If you're blocked, install the official GMGN CLI
and set the `GMGN_API_KEY` environment variable — the scripts will
automatically fall back to the official API (works from any IP; discovery
also requires the CLI).

**Rate limiting**: the scripts sleep 1-2s between requests and back off on
429s. Please don't turn this up — be respectful of the free endpoint.

Note: the open-sourced scripts are a trimmed rewrite of the original
collection pipeline (which used PostgreSQL and mixed GMGN/DexScreener/
GeckoTerminal/Birdeye/Helius as sources). The dataset itself has more
columns than these scripts currently produce, but the core feature and
label logic is the same.

## License

Dataset and code are released under the MIT License. Data is for research
purposes only; **this is not investment advice**. Memecoin trading is
extremely high risk — the original project behind this dataset was
ultimately shelved because live expected value wasn't positive enough.
