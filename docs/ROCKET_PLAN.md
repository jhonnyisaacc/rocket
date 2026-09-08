# ROCKET_PLAN.md

Clean rebuild of NAVE as a bot-runtime-agnostic research engine.

Implementation clarification: [the #12 IE audit](IE_AUDIT.md) supersedes historical
status examples below, including disclosure inboxes, optional corroboration,
Cava validation scope, capture/status primitives and the JSON v2 reason contract.

Status: **PLAN ONLY**. No repo, no code, no cutover.

Inspected as reference (read-only): `/home/david/nave`, `/home/david/agent/deployment/quant_nave/`, ABI provider-gate reports, memecoin collector redesign notes. Nothing in those trees is modified by this plan.

General design corrections folded in (not a single-section nit):

- one **durable test harness** so every workflow is checked the same way on every future PR
- every V1 surface except **memecoin strategy** must actually work and return a complete JSON result any bot can present
- memecoin **strategy** stays exploratory (`NO EDGE VALIDATED`), with primitives left ready
- portfolio inventory is already tracked from a **wallet in the existing environment** — Rocket reads it, never signs
- Rocket **does not delete, unset, or rewrite** environment variables; it consumes the names already there and stays open to new providers
- providers are **modular**, not hardcoded to one vendor or `~/.hermes`

---

# Goals

Rocket is the smallest reliable **read-only research engine** that satisfies Abi's current useful market-research responsibilities, without depending on Hermes, OpenClaw, Nanobot, Discord, or any future assistant runtime.

```text
any bot runtime
      │  argv + env + explicit state paths
      ▼
    ROCKET          READ_ONLY_RESEARCH_ONLY_HUMAN_GATED
      │  JSON ResearchResult on stdout
      ▼
  runtime adapter   (presentation, scheduling, secrets, chat)
```

Rocket owns:

- data acquisition and normalization
- one point-in-time implementation
- evidence with provenance
- research evaluation
- strategy/experiment state that is scientific, not conversational
- missed-opportunity audits
- structured JSON outputs that **any** bot runtime can present
- a single test harness that every workflow and future PR must pass
- **read-only** wallet inventory used as portfolio evidence (existing env/RPC)

Rocket does **not** own: Discord, Slack, chat routing, agent profiles, model selection, cron, user messaging, task orchestration, bot memory/sessions, reminders, systemd/gateway lifecycle, orders, wallet **signing**, mnemonic/vault management, automatic watch mutations, or creating new holdings from unknown mints.

Preserve every scientifically proven NAVE lesson. Do not repair NAVE. Do not rediscover known failures.

---

# Non-goals

- Trading, paper-trading that can become live, alerts-as-orders, wallet vaults, mnemonic handling, or any signing path.
- Deleting or rewriting the user’s existing `.env` / process environment.
- Hardcoding Hermes/OpenClaw/Nanobot paths or a single vendor behind each capability.
- A second language (Rust) until a measured hot path proves Python cannot hold headroom.
- A plugin bus, setuptools entry-point zoo, MCP server, HTTP daemon, or message bus in V1. A **small capability registry** (protocol + toml row) is required so providers are not hardcoded.
- Hermes/OpenClaw/Nanobot adapters inside this repo.
- Big-bang cutover of all workflows.
- Building a memecoin **strategy**. Production fact: **NO EDGE VALIDATED**.
- Automatic `VALIDATED` for options.
- Making Cava a hard dependency of crypto or portfolio.
- Scheduler manifests, Discord chunking, Shabbat/desk calendars, notification fingerprints.
- Generic watch defaults, Quant A1/A2/A4 natural-language responsibilities, or silent `~/.hermes` discovery.
- Reproducing NAVE's ~90 CLI commands, web UI, FastAPI backend, or `hermes/integration.py`.

---

# NAVE lessons

These are proven. Rocket encodes them on day one.

## 1. Point-in-time is one implementation

`event_time` / `available_at` / `decision_time` are the only PIT fields. Rules already tested in `research/core/contracts.py` and `tests/test_research_core.py`:

- event after decision → ineligible (`LATE`)
- available after decision → ineligible (`LATE`)
- missing availability → `UNKNOWN` (never guessed from `event_time`)
- historical replay must never load live context
- no `now()` substituted for historical missing values
- timezone-aware or absent; never naive

`research/memecoin/research_primitives.py:derive_available_at` is the conservative availability helper: event + source latency, never earlier.

## 2. Unknown remains unknown

Nonfinite values, missing identity, missing clocks, and unsupported chains are `UNKNOWN` / `INSUFFICIENT_EVIDENCE`, not a valid empty scan. Encoded in `tests/test_memecoin_identity_integrity.py`.

## 3. Live and replay are different modes

Crypto already has this split (`scan_live` vs `scan_from_fixture`). Replay requires historical observation timestamps. Live discovery failure is `DATA_UNAVAILABLE`, not `NO_SETUP`. Keep the split; delete the duplicate CLI engines (`momentum-scan`, `universe-momentum-scan`, `crypto scan`, `daily`, `playbook`).

## 4. Operational health ≠ research result

This is the most expensive NAVE lesson (ABI provider gates, 2026-09-07).

Healthy examples:

- provider OK + research `NO_SETUP` → healthy
- official OGE/House OK + `NO_NEW_RECORDS` → healthy
- shorts live snapshot OK + missing catalyst/fundamentals → `INSUFFICIENT_EVIDENCE`, not provider failure
- Cava transcript OK + uncorroborated claims → `INSUFFICIENT_EVIDENCE`

Invalid:

- provider unavailable + research `NO_SETUP`
- empty CLI input treated as “no shorts”
- `NO_RECORDS` treated as unproved executive coverage

NAVE started putting `runtime_health` in payloads (`disclosures.py`, `shorts.py`, `portfolio.py` ISM). Rocket makes this a **first-class field**, not a payload convention.

## 5. Source provenance is evidence, not decoration

Official House/OGE vs FMP secondary must stay labeled. Index-added date ≠ disclosure date ≠ transaction date. Filenames do not establish trades. House records are **filings**, not invented trade rows.

## 6. Partial coverage is still a result

Watches: evaluate supported tickers; mark others `UNAVAILABLE`; do not fail the whole run. Crypto: discovery rows without instrument data increment `unavailable_instruments`, they are not silent drops. ISM: headline can be valid while rankings are `PARTIAL`.

## 7. Cava is an optional overlay

`CurrentMacroProvider` (`EFFR`, `WDTGAL`, `RRPONTSYD`, `WALCL`) is the canonical macro. Cava unavailable must not disable crypto or portfolio. Test: `tests/test_quant_usefulness.py::test_core_macro_independent_cava_and_expiry`.

Cava itself: RSS → transcript (Supadata) → claims → corroboration → structured overlay. Cursor must not advance on transcript failure. Partial/stale/contradicted context is not `validated`. Do not persist API keys in results.

## 8. Canonical identity, not tickers

Join key is `chain_id + contract_address/mint` or `canonical_asset_id`. Symbols are labels. Same ticker, two contracts, two outcomes. PONS/MEME case studies are never defaults (`docs/memecoin_snapshot_contract.md`).

## 9. Missed-move evaluation is hindsight-safe

Later outcomes are joined **after** scan. `information_existed_before_move` is `BEFORE_MOVE` / `AFTER_DECISION` / `UNKNOWN`. Rejected candidates stay in the audit. Encoded in `research/crypto_futures.py:analyze_missed_moves`.

## 10. Deterministic watches are not responsibilities

`ABOVE` / `BELOW` / `CROSS_ABOVE` / `CROSS_BELOW` / `ZONE` only. No model. A1/A2/A4 text stays unparsed metadata. CROSS requires a prior observation. Re-arm after price leaves the condition. Partial prices still evaluate supported watches.

## 11. Private portfolio state is caller-owned

Privacy is not market-data unknown. Stale private inventory is not a missing quote. Per-position results: one ticker can `HOLD` while another is `REVIEW_REQUIRED`. Theses remain drafts until a human says otherwise. Rocket never defaults to `~/.hermes/state/portfolio_manager/portfolio.json`.

## 12. ISM identity is explicit

`MANUFACTURING` vs `SERVICES`, `reference_month`, publication time (first/third US business day 10:00 America/New_York). Headline PMI ≠ industry rankings. NMFBAI is Services Business Activity, **not** the Services composite — never substitute. Broad HTML body matching selected August 2022; match roundup identity + publisher release, reject URL/heading disagreement.

## 13. Shorts: bearish macro is never enough

Required non-macro factors. Missing required factor → unknown, not false. Valuation support is evidence **against** a short. Live acquisition must not require a handcrafted JSON for normal use. Replay remains available.

## 14. Options never auto-validate

`EXPERIMENTAL` until explicit human review of sample, costs, regime stability. Metrics `GROSS_UNCOSTED`. Crypto options and equity options stay separate.

## 15. Memecoin collector: capture is not analysis

Failed architecture: WebSocket → participant expansion → SQLite → outcomes → checkpoint → next frame. SQLite insert/page I/O caused `MAX_QUEUE_DEPTH` overflow (gate 02/03). Proven redesign (committed primitive `research/nave/raw_capture_spool.py`, **not deployed**):

```text
NETWORK → minimal lossless durable append/spool   (hot path)
spool   → normalize → participants → Parquet → analysis   (async)
```

Acknowledgement = fsync of bytes + directory, not downstream completeness. No Kafka/Redis unless a later benchmark requires it.

## 16. Models are rare

Watches, universe filters, PIT joins, statistics, and price acquisition are deterministic. Models belong only in Cava synthesis / narrative overlays — and even Cava today is rule+FRED corroboration. Grok/X research arrives as **external structured evidence**, not an in-process dependency.

## 17. Presentation is not research

`research/quant_runner.py` currently: requires Discord `channel_id`, writes under Hermes profile dirs, applies desk Shabbat calendar, subprocesses CLI, emits Spanish Discord text, suppresses repeats via fingerprint. **All of that is adapter work.** Rocket prints JSON.

Current production invocation (do not copy):

```bash
# /home/david/agent/deployment/quant_nave/crypto.sh
python -m cli.main research run --workflow crypto \
  --state-dir /home/david/.hermes/profiles/quant/nave-research \
  --channel-id 1514695031901126727
```

---

# Disposition matrix

Legend: **KEEP IDEA** = encode the lesson. **PORT CODE** = copy/adapt a clean module. **REWRITE** = reimplement smaller. **DROP** = do not inherit.

| NAVE capability/component | KEEP IDEA | PORT CODE | REWRITE | DROP | Reason |
|---|---|---|---|---|---|
| `ResearchResult` / `ResearchStatus` / `EvidenceReference` / `PointInTime` (`research/core/contracts.py`) | ✓ | ✓ slim | | | The actual shared contract. Strip `StateOwner.ABI_ORCHESTRATION`, Discord markdown, `generated_at` defaulting to `now()`. Promote operational status. |
| `SafetyBoundary.READ_ONLY_RESEARCH_ONLY_HUMAN_GATED` | ✓ | ✓ | | | Non-negotiable on every result. |
| `ResearchStore` atomic JSON | ✓ | | ✓ | | Keep atomic write. Do not overwrite `results/{workflow}.json` as the only journal — use `runs/{run_id}/`. |
| `run_phase` strategy protocol (`scan/evaluate/missed_moves/status`) | ✓ | ✓ | | | Optional phases; no abstract base class ceremony. |
| Current macro `EFFR/TGA/RRP/WALCL` (`research/core/macro.py`) | ✓ | ✓ | | | Canonical macro, Cava-independent. Replace pandas at the edges with records→Polars later. |
| Macro usable/expiry (`macro_is_usable`, 6h context, factor age caps) | ✓ | ✓ | | | Fail closed on missing/future/stale factors. |
| Equity session clock (`research/core/market_clock.py`) | ✓ | ✓ | | | NYSE holidays/early close; observation freshness ≠ retrieval time. |
| Cava RSS parse, cursor, fail-closed transcript (`research/cava/`) | ✓ | ✓ | | | Strip `HERMES_HOME` dotenv. Secrets from env only. |
| Cava corroboration vs FRED (`research/cava/corroboration.py`) | ✓ | ✓ | | | Conservatism, contradictions, no social feed required. |
| Supadata transcript provider | ✓ | ✓ | | | Keep API contract; drop profile-secret discovery. |
| Crypto futures funnel (`research/crypto_futures.py`) | ✓ | ✓ extract | | | One engine: universe→eligible→liquid→momentum→derivatives→macro→COT→optional Cava. |
| Crypto live vs fixture split | ✓ | ✓ | | | Explicit `--replay`; never mix clocks. |
| COT as **market regime**, not altcoin signal (`research/crypto_cot.py`, `cot_regime_passes`) | ✓ | ✓ | | | BTC/ETH COT once. Unknown COT ≠ NO_SETUP by itself. |
| Canonical crypto identity (`trading/crypto/momentum/universe.py`) | ✓ | ✓ extract | | | No ticker-only joins. |
| Current universe discovery (CoinGecko + Hyperliquid join) | ✓ | | ✓ read-only extract | | Port the **read path** only. Leave `HyperliquidClient` wallets, `execution_plan`, thesis store. |
| Momentum ranking thresholds (`discovery.py` DiscoveryConfig) | ✓ | ✓ config | | | Keep as data, not a second engine. |
| Missed-move analyzer | ✓ | ✓ | | | Hindsight-safe. |
| Duplicate crypto CLIs (`scan`, `momentum-scan`, `universe-momentum-scan`, `daily`, `playbook`, `position-review`) | | | | ✓ | PR41 superseded by PR44 (`docs/CRYPTO_PR41_DISPOSITION.md`). |
| `trading/crypto/analysis/*` (squeeze, capitulation, regime thesis, daily_display) | | | | ✓ | Abandoned/parallel strategies. |
| `trading/crypto/theory_v2.py`, `signals.py`, `strategy.py`, `execution.py` | | | | ✓ | Execution and old theory loop. |
| `trading/crypto/wallet_service.py`, `vault.py`, `chain_audit.py` | | | | ✓ | Wallet/signing. |
| Portfolio review per-position (`research/portfolio.py`) | ✓ | | ✓ | | Keep actions and evidence shape. Remove Hermes default path, ledger refresh, Quant watch fallback. |
| Thesis attach as **draft** (`research/portfolio_theses.py`) | ✓ | | ✓ | | Caller supplies thesis file. Do not scrape A1 from Quant watch store. |
| `PortfolioContextProvider` (OpenBB/YF/FMP) | ✓ | | ✓ | | Plain provider functions. OpenBB at boundary only. |
| Deterministic `check_watch` | ✓ | ✓ | | | Conditions set is correct. Drop default `ZONE` when condition missing (that default is debris). |
| `research/quant_state.py` Hermes watch adapter | ✓ unparsed-responsibilities lesson | | | ✓ module | Adapter belongs in Agent. Rocket accepts already-canonical watches. |
| ISM identity/publication gate (`trading/stocks/ism_identity.py`) | ✓ | ✓ | | | First/third business day 10:00 NY. |
| ISM scraper headline vs rankings (`ism_scraper.py`) | ✓ | ✓ | | | Roundup identity; no sub-index lists; no NMFBAI substitution. Playwright optional, not architecture. |
| ISM industry→GICS mapping (`trading/stocks/mapping.py`) | ✓ | ✓ | | | Conservative mapping; drop rather than guess. |
| `ism_equity_pipeline` mixed into portfolio.candidates | | | ✓ split | | Rocket: `rocket ism` is its own workflow. Portfolio does not secretly run ISM. |
| Duplicate stocks CLI (`ism-scan`, `ism-report`, `ism-equity-pipeline`, `ism-calendar`, `screen`) | | | | ✓ | One ISM command. |
| Official House + OGE providers (`research/disclosure_providers.py`) | ✓ | ✓ | | | Filing-level; schema/freshness/pagination checks. |
| FMP secondary fallback | ✓ | ✓ | | | Labeled secondary, never “official”. |
| Disclosure normalize + seen-cursor (`research/disclosures.py`) | ✓ | ✓ | | | `NO_NEW_RECORDS` vs provider failure. Not a buy signal. |
| Short factor model (`research/shorts.py`) | ✓ | ✓ | | | Macro-only rejection; missing→unknown; rejected retained. |
| Autonomous short snapshot (`research/short_providers.py`) | ✓ | ✓ | | | Live default; replay via `--fixture`. Tiny universe is a V1 research universe, not holdings. |
| Options research contract (`research/options.py`) | ✓ | ✓ | | | Never auto `VALIDATED`. Separate crypto/equity domains. |
| `options/` package (gem_finder, walkforward, visualization, ticker_registry, eth_weekly, journal_learning) | | | | ✓ | Experimental debris; 10k LOC. |
| Memecoin canonical identity + discover/evaluate/missed (`research/memecoin_workflow.py`) | ✓ | ✓ | | | Research primitives only. Keep overfit guard. |
| `research/memecoin/research_primitives.py` | ✓ | ✓ | | | Offline PIT audits. |
| Frozen experiment JSON contracts under `research/nave/experiments/` | ✓ as references | copy as docs/fixtures | | | Not executable strategy. |
| `research/nave/state.json` “NO EDGE VALIDATED” | ✓ | | | live file | Status is a **result field**, not a mutable project diary inside the engine. |
| Outcome taxonomy (`outcome_taxonomy.py`) | ✓ | ✓ | | | Explicit unresolved classes; unknown is not failure. |
| Raw capture spool (`research/nave/raw_capture_spool.py`) | ✓ | ✓ | | | The collector lesson, already isolated. |
| Prospective collector (`prospective_collection.py`, `prospective_runtime.py`) | lesson only | | ✓ spool-first | ✓ current pipeline | Do not take a fourth gate on WS→SQLite. |
| Dune SQL + materializer | keep as optional research | later | | V1 default | V1 memecoin collect is local spool; Dune is paid and gated. Do not make Rocket depend on Dune credits. |
| Resource guard for paid APIs | ✓ | ✓ slim | | | Fail-closed preflight. Not a scheduler. |
| `research/orchestration.py` Discord chunking / `present_result` | | | | ✓ | Adapter. |
| `research/quant_runner.py` channel_id + Shabbat + subprocess | | | | ✓ | This **is** the coupling. |
| `research/quant_presentation.py` Spanish Discord summaries | | | | ✓ | Adapter may reimplement **from JSON**. |
| Notification fingerprint suppress | | | | ✓ from Rocket | Adapter concern. |
| `hermes/integration.py` (~2k LOC), `cli/commands/hermes.py` | | | | ✓ | Runtime-specific. |
| `cli/commands/core.py` trading/api/mcp/journal | | | | ✓ | Out of bounds. |
| `cli/commands/wallet.py` create/setup/claim/fund/test-trade | | | | ✓ | Signing/funding. Read-only inventory is a **provider**, not this CLI. |
| `backend/app` FastAPI + OpenBB service | OpenBB record helper | extract `_to_records` | | rest | No HTTP API in V1. |
| `web/` | | | | ✓ | |
| `ops/quant_nave_jobs.json`, plist examples | | | | ✓ | Scheduler knowledge. |
| `scripts/_n5_*`, squeeze/theory/momentum loops | | | | ✓ | Rejected/one-off experiments. |
| `scripts/daily_scan.py`, `monitor_entry_zones.py` | | | | ✓ | Alert/trading path. |
| `scripts/setup_wallets.py`, `wallet_vault.py`, `show_mnemonic.py` | | | | ✓ | |
| `trading/brokers/`, `trading/alerts/`, `trading/journal/` | | | | ✓ | |
| `trading/stocks/operational_calendar.py` (Shabbat) | | | | ✓ from Rocket | Desk policy belongs in Agent. |
| `trading/stocks/portfolio_ledger.py` read-only ONDO/Solana inventory | ✓ | ✓ extract | | `~/.hermes` default | Wallet-tracked portfolio already exists in the environment. Port the **read-only** refresh (no sign, no create-position, no thesis overwrite). Address/RPC from env + caller state. Drop Hermes path default. |
| `docs/analysis/*` iteration reports, QUANT_NAVE_PR_* reports | | | | ✓ from runtime | Historical; do not port into Rocket docs as living spec. |
| `docs/hermes/*` | | | | ✓ | |
| `AGENTS.md` theory refinement loop | | | | ✓ | |
| Generic watch defaults / documentation examples as live watches | | | | ✓ | Provenance lesson: `ARBITRARY_IMPLEMENTATION_DEFAULT` is not user state. |
| Wrapper `research run --channel-id` | | | | ✓ | |
| Worktree copies (`.worktrees`, 7208 extra py files) | | | | ✓ | |
| pandas as core dataframe layer | | | | ✓ as default | Polars + Parquet + DuckDB. pandas only at OpenBB boundary. |
| Discord tests (`tests/test_discord_presentation.py`) | | | | ✓ | |
| `tests/test_hermes_integration.py` | | | | ✓ | |
| Contract/PIT/watch/macro/disclosure/ISM/shorts/crypto funnel tests | ✓ as spec | rewrite against Rocket | | | Do not lose invariants. |

---

# V1

V1 exists to replace the **currently useful** Abi/Quant research jobs, plus the two isolated research surfaces.

## Feature count: 12 surfaces

| # | Surface | CLI | Production posture |
|---|---|---|---|
| 1 | Shared research contract | (all commands) | **must work** — harness-enforced |
| 2 | Canonical macro context | `rocket macro` | **must work** — any bot can present the JSON |
| 3 | Cava overlay | `rocket cava` | **must work**, optional downstream |
| 4 | Crypto futures | `rocket crypto scan` | **must work** — live universe is **top 100** by market cap plus liquid perps |
| 5 | Portfolio review | `rocket portfolio review` | **must work**, wallet inventory is an input |
| 6 | Deterministic watches | `rocket watch check` | **must work** |
| 7 | ISM | `rocket ism` | **must work** |
| 8 | Public disclosures | `rocket disclosures` | **must work** |
| 9 | Stock shorts | `rocket shorts` | **must work** |
| 10 | Strategy evaluation / missed moves | `rocket crypto evaluate`, `rocket crypto missed` | **must work** as research lifecycle |
| 11 | Options | `rocket options scan`, `rocket options evaluate` | **must work** as experimental research; unschedulable; never auto-`VALIDATED` |
| 12 | Memecoin primitives | `rocket memecoin status\|collect\|scan\|evaluate` | primitives **must work**; **strategy not shipped** (`NO EDGE VALIDATED`) |

Plus `rocket status` (operational index, not a 13th research surface).

**“Must work”** means: live acquisition path, fixture tests in the shared harness, complete `ResearchResult` JSON (evidence, operational vs research status, warnings). Not a stub. Any bot parses the same JSON.

## Out of V1

- Memecoin **strategy**, scoring, recommendations, cron. Primitives stay so exploration can continue. Tracked as a Rocket repo issue, not silent.
- Options **strategy** as a scheduled/live job. Scan/evaluate primitives stay. Tracked as a Rocket repo issue documenting why stocks and crypto options did not validate.
- Crypto futures **strategy polish** beyond the live top-100 scan. Tracked as a Rocket repo issue. The scan itself is V1 production.
- Dune paid materialization as a default path.
- HTTP/Unix server.
- Any bot adapter (presentation/scheduling stay outside).
- Second crypto engine.
- Portfolio “candidates” command (ISM already produces rankings; portfolio reviews **holdings**).
- Wallet create/sign/fund/trade CLIs.

---

# Tracking issues (opened when the Rocket repo is created)

Not integrating a strategy into live agent jobs does **not** mean forgetting why. Phase 0 opens these three GitHub issues in `rocket` and leaves them open. Issue bodies are seeded from NAVE evidence, not rediscovered later.

## Issue 1 — Options strategy (stocks **and** crypto): why it did not work

**Title:** `Options strategy not validated — do not schedule (crypto + equity)`

**Why it is not live:**

- Crypto (BTC/ETH) and equity options were separate domains, but neither produced a validated edge. `research/options.py` always stays `EXPERIMENTAL`; evaluate **cannot** write `VALIDATED`.
- Reported metrics are `GROSS_UNCOSTED`: no fees, spread, assignment, pin risk, or crypto options funding in the P&L. A positive mean return is not an edge.
- No autonomous live options snapshot path comparable to shorts. Normal use required handcrafted snapshots; missing IV/RV/`defined_risk` or late `available_at` → `INSUFFICIENT_EVIDENCE`, so a PIT live series never accumulated.
- The large `options/` package (gem finder, walkforward, visualization, ticker registry, `nave options opportunities`, Hermes `options_scan`) was a parallel platform, not a scientific result. Merge-readiness even treated tiny samples (`trades >= 2–3`) as “approved” — that is overfitting, not validation.
- n=30 and mean>0 was explicitly rejected as a PROMISING gate (`docs/GROK_REVIEW_RESOLUTION_LEDGER.md` nave-48).
- Stale volatility (>1 day), unknown availability, and out-of-scope underlyings (e.g. SOL on the BTC/ETH crypto definition) fail closed.

**Keep in Rocket:** `rocket options scan|evaluate` as research primitives, unschedulable, never auto-`VALIDATED`.

**Do not:** enable a Quant/cron job, mix stocks and crypto chains, or port gem-finder/walkforward as if they were the strategy.

## Issue 2 — Memecoin strategy: no edge, keep exploring on primitives

**Title:** `Memecoin strategy — NO EDGE VALIDATED; primitives only`

**Why it is not live:**

- Canonical state: **NO EDGE VALIDATED** (`research/nave/state.json`). M3 statistical sanity was **inconclusive** (Day-2 event panel not exported; A/B/C/D not estimated).
- Participant self-flow contaminated raw flow (~47% of a first-30-minute slice). Unknown must stay unknown.
- Collector architecture failed: WebSocket → SQLite insert/page I/O → `MAX_QUEUE_DEPTH` overflow. Redesign is spool-first; strategy work is blocked on stable capture.
- Only a handful of comparable event days; PONS/MEME case studies are not defaults; symbols are not join keys.
- Python cannot win launch-block sniping; that was never the research claim.

**Keep in Rocket:** `memecoin collect|scan|evaluate|status` primitives + raw spool. Status always carries `edge: NO_EDGE_VALIDATED`.

**Do not:** schedule a Discord/strategy job, inspect holdout as health, or add asset-specific overfit rules.

## Issue 3 — Crypto futures strategy: live top-100 scan, keep polishing

**Title:** `Crypto futures strategy polish — live scan is top-100; edge not validated`

**What V1 does live:** `rocket crypto scan` on the **current top 100 by market cap** plus liquid perps (same funnel as NAVE PR44). That job **is** production.

**Why the strategy still needs an issue:**

- Evaluate still reports research-only / not validated; bounded out-of-sample, fees, funding, and slippage are not a proven executable edge.
- Historical duplicate engines (legacy `crypto scan` / `momentum-scan` / PR41) are dropped; polish happens **on the one funnel**, not a new scanner.
- Tickers outside the point-in-time top 100 must stay excluded (replay PONS lesson).
- COT is market regime, not an altcoin signal; Cava is overlay only.
- Missed-move audits exist to find blind spots; they must not be fed back into the live scan as hindsight.

**Keep exploring on that issue:** filter thresholds, liquidity/OI, paper-cost realism, OOS evaluate, missed-move systematic gaps — without a second production owner.

---

# Live agent tasks after cutover

This is the operational catalog: what a bot (Hermes, OpenClaw, Nanobot, or later) actually runs live. Rocket never chats, never posts, never trades. The adapter runs a command, parses JSON, and presents it to you. You decide.

Same loop every time:

```text
schedule or user ask
    → adapter runs `rocket <workflow> --json` (+ env already in this machine)
    → JSON ResearchResult
    → adapter presents (Discord/chat)
    → human gates any action
```

Current Quant cadence is the starting schedule. Rocket does not own cron; the adapter keeps the clocks.

## A. Live scheduled research (production)

These replace today’s enabled Quant/NAVE jobs. They must work.

| # | What you get | Rocket command | Typical cadence (adapter) | Bot presents | You do |
|---|---|---|---|---|---|
| 1 | Price alerts on explicit watches | `rocket watch check --watches PATH` | 3× daily | ticker, condition, price, only when a rule **enters**; silent if nothing new | confirm / ignore; watches stay yours |
| 2 | Cava video overlay | `rocket cava` | daily ~18:00 BA | claims + corroboration + contradictions, or “no new video” | use as optional macro color, not a trade |
| 3 | Canonical US rates/liquidity | `rocket macro` | with crypto/portfolio, or explicit | EFFR/TGA/RRP/WALCL, regime, staleness | context only |
| 4 | Crypto futures scan | `rocket crypto scan` | 6-hourly | **top 100** market-cap universe + liquid perps; funnel + candidates or healthy `NO_SETUP` | human entry/exit only; strategy polish is a repo issue, not a second engine |
| 5 | Portfolio review | `rocket portfolio review --state PATH [--refresh-inventory]` | daily | per-holding HOLD / review / reduce / exit + evidence; wallet quantities are read-only | you change holdings, not Rocket |
| 6 | ISM manufacturing + services | `rocket ism` | month days 1–7 after publication | headline vs rankings, reference month, partial lists explicit | research / candidate ideas, not orders |
| 7 | Official political filings | `rocket disclosures` | weekdays | new filings **or** healthy `NO_NEW_RECORDS` | delayed context, never a buy signal |
| 8 | Stock-short scan | `rocket shorts` | weekdays | candidates only if enough non-macro factors; missing factors stay unknown | research only |

If a provider is down, the bot must show **operational failure**, not “no setup.” If providers are fine and there is nothing to do, the bot shows **no setup** and that is success.

## B. On-demand (you ask the agent)

Same JSON contract. Not necessarily cron.

| # | What you ask | Rocket command | Notes |
|---|---|---|---|
| 9 | “What’s the latest research health?” | `rocket status` | last run per workflow, operational vs research |
| 10 | “Did last crypto scan work out?” | `rocket crypto evaluate --outcomes PATH` | later results vs that scan |
| 11 | “What did we miss?” | `rocket crypto missed --outcomes PATH` | hindsight-safe; does not change the scan |
| 12 | Options research | `rocket options scan` / `evaluate` | experimental; **never** auto-validated; **not** scheduled |
| 13 | Refresh book from the wallet then review | `rocket portfolio review --state PATH --refresh-inventory` | read-only chain; existing env RPC; no signing |

## C. Ready, but not a live strategy job

| # | What exists | Rocket command | Live with an agent? |
|---|---|---|---|
| 14 | Memecoin capture + primitives | `rocket memecoin status\|collect\|scan\|evaluate` | **No production strategy job.** Collect/scan/evaluate exist so exploration can continue. Status always `NO EDGE VALIDATED`. Do not Discord-spam this. |

## D. Never live in Rocket (stay outside or gone)

- Orders, signing, vault, mnemonic, Hyperliquid place/cancel
- Discord/Slack routing, channel IDs, Shabbat calendar, notification fingerprints
- Creating watches or holdings automatically
- A1/A2/A4 natural-language “responsibilities” mixed into price rules
- Duplicate NAVE scanners (`momentum-scan`, `ism-report`, `politicians-scan`, gem finder, …)

## Mapping from today’s jobs

| Today (adapter → NAVE) | After cutover (adapter → Rocket) |
|---|---|
| `quant_nave/watch.sh` → `nave research run --workflow watch --channel-id …` | `rocket watch check --watches PATH --json` |
| `cava.sh` → cava daily | `rocket cava --json` |
| `crypto.sh` → crypto futures scan | `rocket crypto scan --json` |
| `portfolio.sh` → portfolio review | `rocket portfolio review --state PATH --json` |
| `ism.sh` | `rocket ism --json` |
| `disclosures.sh` | `rocket disclosures --json` |
| `shorts.sh` | `rocket shorts --json` |
| (macro implicit) | `rocket macro --json` (explicit) |
| memecoin.sh disabled | stays disabled as strategy; primitives available |

One workflow, one owner. The bot only needs: run command → parse JSON → present.

---

# Bot-runtime boundary

## One integration: CLI → JSON

HTTP does not improve reliability for a local research process. A daemon would make Rocket own lifecycle, which it must not. V1 is a process:

```bash
rocket crypto scan --json
rocket portfolio review --state PATH --json
rocket watch check --watches PATH --json
```

Contract:

1. Adapter **may** export secrets; Rocket also uses secrets **already present** in the process environment. Rocket never deletes, unsets, or rewrites those variables or foreign `.env` files.
2. Adapter passes explicit state paths when it has them.
3. Adapter sets `ROCKET_HOME` if not `~/.rocket`.
4. Adapter parses stdout JSON. Stderr is logs, never the result. **Every production workflow emits the same result type**, so any bot can present it.
5. Adapter presents, chunks, translates, schedules, and delivers.
6. Adapter owns desk calendar, Discord channel IDs, profile env, retries-of-delivery.

Rocket never: reads `~/.hermes`, `~/.openclaw`, `~/.nanobot`; loads `HERMES_HOME/.env`; accepts `--channel-id`; emits `discord_text`.

## Exit codes follow **operational** status

| Exit | Meaning |
|---|---|
| 0 | Operational `HEALTHY` or `PARTIAL`; research may be `NO_SETUP` |
| 2 | Operational `UNAVAILABLE` (providers failed; research must not claim `NO_SETUP`) |
| 1 | `ERROR` (bug, invalid invocation, corrupt state) |

This is how bots stop treating empty research as a crash.

## Adapter ownership (outside this repo)

| Runtime | Adapter location | Responsibility |
|---|---|---|
| Hermes | Agent `deployment/quant_nave/*.sh` + profile env | Replace `nave research run --channel-id` with `rocket … --json`, then existing Discord presenter |
| OpenClaw | OpenClaw tool wrapper | argv/env only |
| Nanobot | Nanobot plugin | argv/env only |
| Future | same | command → JSON |

Never two permanent production owners of a workflow. See Incremental migration.

---

# Technical stack

Python-first, one language.

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | matches current NAVE venv |
| CLI | Typer, tiny | JSON default |
| HTTP | httpx | sync in workflows; asyncio only in memecoin collector |
| JSON | orjson | stdout + run journal |
| Tables | Polars | |
| On-disk research | PyArrow Parquet | |
| Analytical SQL | DuckDB | against Parquet |
| Small state | SQLite **or** atomic JSON | cursors, seen-ids, last quotes for CROSS; **not** event firehose |
| Capture | append-only JSONL spool + fsync | port `RawCaptureSpool` |
| Macro transport | OpenBB if present, else FRED HTTP | no hard OpenBB-extension zoo |
| Lint | ruff | |
| Tests | pytest | fixtures, no live Discord |

**Rust:** forbidden in V1. Revisit only with a benchmark showing the Python spool/collector cannot sustain the pumpapi burst with ≥2× headroom vs the failed SQLite path.

**pandas:** allowed solely as an OpenBB/`to_df()` boundary, converted immediately to records/Polars.

**asyncio:** collector WebSocket + spool writer only. Do not asyncio-wash every provider.

---

# Data/state architecture

## Directories

Default root: `$ROCKET_HOME` else `~/.rocket`.

```text
~/.rocket/
  runs/{utc_date}/{run_id}/
    result.json          # immutable ResearchResult
    meta.json            # argv, workflow, mode, git sha if available
  contexts/
    macro.json           # latest canonical macro snapshot
    cava.json            # latest overlay (may be invalidated)
  state/
    cava_cursor.json     # processed video ids
    cava_attempts.json   # retry fairness without advancing cursor
    disclosures_seen.json
    watch_last_quotes.json  # CROSS/re-arm only; not user watch definitions
    memecoin_status.json
  cache/
    fred/{series}.parquet
    quotes/
    hl/
  spool/
    memecoin/            # raw capture segments; never auto-delete
```

## Ownership / lifetime

| Path | Owner | Lifetime |
|---|---|---|
| `runs/` | Rocket | append-only; no overwrite of a `run_id` |
| `contexts/` | Rocket | latest snapshot; invalidated in place; not the journal |
| `state/` | Rocket | operational indexes; small |
| `cache/` | Rocket | disposable; may be deleted without changing science |
| `spool/` | Rocket | durable evidence; deletion is an explicit operator act |
| User portfolio JSON | **caller** | authority for theses/names; Rocket does not copy it into `~/.rocket` as source of truth |
| User watches JSON | **caller** | same |
| Thesis markdown | **caller** | same |
| Wallet inventory (read-only) | chain + env RPC | evidence of quantities; does not create positions or overwrite theses |

No second authority for theses. Rocket may cache **market** evidence. Wallet inventory is evidence fused into the caller-owned portfolio file only when `--refresh-inventory` is explicit.

## Dataset rules

- Research panels: Parquet.
- Query: DuckDB.
- Run results: JSON (orjson).
- SQLite: optional for `state/` if JSON files contend; never for capture.
- `ResearchStore.save_result` in NAVE overwrites `results/{workflow}.json` — **do not copy that**. Latest pointer may exist, but the run journal is the source of truth.

## Config

`config/providers.toml` (in-repo, no secrets, no home paths):

- capability → primary provider + ordered fallbacks
- env names each provider reads (and aliases)
- series ids, age caps, universe size, ISM URLs, House/OGE endpoints, factor lists, watch condition enum
- inventory: chain/RPC capability, not a Hermes path

`config/env.toml` maps **capabilities to environment variable names already used in this environment**, plus Rocket aliases. Adding a provider is a new module + a row here, not a workflow rewrite.

Runtime env — **read, never delete**:

```text
# Rocket
ROCKET_HOME
ROCKET_PORTFOLIO_STATE
ROCKET_WATCH_STATE
ROCKET_INVENTORY_ADDRESS     # optional; else address from --state file

# Already in the environment — keep using these names
FRED_API_KEY
FMP_API_KEY
SUPADATA_API_KEY             # alias SUPADATA_API_TOKEN
HELIUS_API_KEY               # Solana read RPC for inventory
MASSIVE_API_KEY              # optional fundamentals
HL_WALLET                    # read-only identity label if needed; never signing
# plus SOLANA_RPC_URL / public RPC fallbacks as configured

# Migration aliases so existing adapters keep working
NAVE_PORTFOLIO_STATE_FILE    # alias of ROCKET_PORTFOLIO_STATE
NAVE_QUANT_WATCH_STATE_FILE  # alias of ROCKET_WATCH_STATE
NAVE_RESEARCH_STATE_DIR      # alias of ROCKET_HOME
```

Rules:

- Rocket **does not** `os.environ.pop`, rewrite `.env`, or require renaming keys as a cutover step.
- Missing secret → that **provider** is `UNAVAILABLE`, not a process crash (unless the workflow has no remaining provider).
- Signing-related keys (`ALPACA_*`, vault mnemonics, `HL_MAX_POSITION_USD`) may exist in the environment; Rocket **ignores** them for execution.
- Hermes-specific discovery (`HERMES_HOME/.env`) stays out. If the adapter already exported `SUPADATA_API_KEY` into the process, that is enough.

---

# Providers

Modular, not hardcoded.

```text
workflow
  → capability protocol (Quotes, MacroSeries, Inventory, …)
  → registry (providers.toml)
  → primary, then fallbacks
  → frozen dataclass
```

This is a **small explicit registry**, not a plugin bus: no setuptools entry points, no dynamic code loading from random paths, no provider-framework metaclasses. Workflows import protocols, not `yahoo.py`.

Adding a provider later:

1. implement the protocol in `rocket/providers/<name>.py`
2. declare it in `config/providers.toml` (capability, env names, fallbacks)
3. add recorded-fixture tests under `tests/providers/`
4. no workflow rewrite unless the **capability** itself is new

| Capability | V1 primary | Fallback | Port from | Notes |
|---|---|---|---|---|
| MacroSeries | OpenBB FRED | FRED CSV | `research/core/macro.py`, OpenBB `_to_records` | Cava corroboration uses the same capability |
| Quotes / history | Yahoo chart | (slot open) | `research/equity_quotes.py` | listed equity/ETF identity checks |
| Fundamentals | FMP | Massive if env present | FMPClient | never labeled official |
| Universe | CoinGecko | (slot open) | current-universe discovery | live only |
| Perps | Hyperliquid **market** reads | (slot open) | extract read methods | no signing; `HL_WALLET` is not an order path |
| COT | OpenBB CFTC | official CFTC | `research/crypto_cot.py` + analyzer/fetcher | market regime, not alt signals |
| ISMRelease | publisher HTML | (none for rankings) | `ism_scraper.py`, `ism_identity.py` | headline may use FRED NAPM; never NMFBAI as composite |
| DisclosuresOfficial | House + OGE | — | `disclosure_providers.py` | filing-level |
| DisclosuresSecondary | FMP | — | FMP house/senate | labeled secondary |
| Transcript | Supadata | (slot open) | `SupadataTranscriptProvider` | env key already in process |
| Inventory | Solana/ONDO read-only | dual public RPC agree-empty | `portfolio_ledger.py` minus Hermes default | wallet-tracked book; no sign; no create-position |
| MemecoinCapture | PumpAPI WS | — | new collector + spool | not a strategy |
| Caller files | portfolio, watches, fixtures | — | — | theses/watches still caller-owned |

Partial coverage is first-class: each provider returns `{status, retrieved_at, failure_kind?, records}`.

V1 ships the rows above. New vendors fill empty fallback slots without touching workflow code.

---

# Workflows

Every workflow returns the same `ResearchResult`. Payload is workflow-specific. No extra status enums per workflow.

Shared validation (engine-level):

- `SETUP_FOUND` requires ≥1 evidence reference `ELIGIBLE` at result `decision_time`.
- `NO_SETUP` **illegal** if `operational.status == UNAVAILABLE`.
- `ERROR` requires ≥1 warning.
- `mode=REPLAY` refuses live context loads and refuses `now()` for missing stamps.
- `safety_boundary` always `READ_ONLY_RESEARCH_ONLY_HUMAN_GATED`.
- `execution_enabled` always false (if present, must be false).

## `rocket status`

Index of latest run per workflow: operational status, research status, `decision_time`, `run_id`. Optional `--ping` for provider probes (not default; probes are not research).

## `rocket macro`

Produce `current_macro_v1`: factors, 4w changes, rates regime (falling/supportive, rising/restrictive, unchanged/neutral), net liquidity when all OK. Persist `contexts/macro.json`. Cava not consulted.

## `rocket cava`

RSS → newest unprocessed video → transcript → claims → FRED corroboration. Cursor advances **only** on fully validated overlay. Payload includes `cursor_advanced`, `corroboration_status`, contradictions. Downstream workflows **may** read overlay; they must run without it.

## `rocket crypto scan`

Live default universe is **top 100 crypto assets by market cap**, joined to **liquid perpetual** markets (NAVE `universe_size=100` / CoinGecko + Hyperliquid). Not a hand-picked coin list. Symbols outside that point-in-time top 100 stay out (PONS-in-replay lesson).

```text
current top-100 universe → eligible → liquidity → momentum → derivatives
  → macro (required for candidate) → COT (regime filter) → optional Cava
  → candidates
```

`--replay --fixture --start --end` is a separate code path sharing the funnel. Cava missing: overlay status `unavailable`, scan continues. Macro missing: no candidates; operational `PARTIAL`/`UNAVAILABLE`; research `INSUFFICIENT_EVIDENCE`, not `NO_SETUP`.

Evaluate remains research (`STRATEGY` not auto-validated). Further strategy polish is **issue #3**, not a duplicate scanner.

## `rocket crypto evaluate` / `rocket crypto missed`

Evaluate persisted scan vs later outcomes. Missed moves never feed the scan. `--outcomes PATH`.

## `rocket portfolio review`

`--state PATH` required (file or API-equivalent JSON) for **theses and book names**.

Wallet tracking already exists in this environment (ONDO/Solana read-only ledger, `HELIUS_API_KEY` / RPC). Rocket uses that as an **Inventory** provider:

- Default: review the supplied state snapshot (offline/fixture safe).
- `--refresh-inventory`: read-only chain query; update **quantities on existing names only**; never create positions; never overwrite `thesis_status`; never sign or send.
- Address from the state file or `ROCKET_INVENTORY_ADDRESS`. RPC from existing env (`HELIUS_API_KEY` or configured RPC URLs). Dual-RPC agree-empty rule from NAVE is kept.
- Unknown `*ondo` mints stay `pending_review`, not invented tickers.

Per position: inventory evidence + price/history + macro + sector + supported company evidence + thesis/invalidation **as recorded**. Actions: `HOLD` / `REDUCE_CANDIDATE` / `EXIT_CANDIDATE` / `REVIEW_REQUIRED`. Missing private state ≠ missing market evidence (`CALLER_STATE_MISSING`). Incomplete chain history is `incomplete_history`, not a fake HOLD.

## `rocket watch check`

`--watches PATH` required. Conditions: `ABOVE|BELOW|CROSS_ABOVE|CROSS_BELOW|ZONE`. Acquire quotes for those tickers. Partial evaluation required. Invalid watch rows listed, not crashed. `model_escalation: false`. Unparsed caller metadata (if any) is echoed, never evaluated.

## `rocket ism`

Fetch Manufacturing and Services independently. Payload identity: `report_type`, `reference_month`, `expected_reference_month`, `publication_at`, `release_status`. Separate `headline` and `industry_rankings` (each with own status). Rankings missing → `PARTIAL`, do not invent. Optional conservative industry→company mapping in payload; not a trade list.

## `rocket disclosures`

Official House + official OGE; FMP secondary if configured. Distinguish:

- operational healthy + `payload.research_result = NO_NEW_RECORDS` → research `NO_SETUP`
- operational unavailable → research must not be `NO_SETUP`
- new filing records → `INSUFFICIENT_EVIDENCE` (context, **not** a setup/buy)

Do not invent owners, transaction dates, or trade rows.

## `rocket shorts`

Live snapshot autonomous (default small liquid universe, not holdings). Replay via `--fixture`. Missing factor remains unknown. Bearish macro alone cannot select. Rejected candidates retained.

## `rocket options scan|evaluate`

Research only. Domain `crypto|stocks` stay **separate**. Strategy state in **payload** (`EXPERIMENTAL|PROMISING|REJECTED`); research status `INSUFFICIENT_EVIDENCE` until a human explicitly records `VALIDATED` in caller-owned metadata — Rocket itself **never** writes `VALIDATED`. Not a live agent job. Tracked as **Issue 1**.

## `rocket memecoin *`

See next section. Status always carries `edge: NO_EDGE_VALIDATED`.

---

# Memecoin architecture

## Scientific posture

`NO EDGE VALIDATED`. Frozen experiment contracts are **references**, not a strategy to ship. PONS/MEME case studies are never defaults. Identity is chain+address. Duplicate snapshot identity is rejected.

Leave the **strategy** unbuilt so exploration can continue on top of working primitives. Do not disable collect/scan/evaluate; do not schedule a strategy job; do not claim edge. Tracked as **Issue 2**.

V1 primitives only:

1. **collect** — hot path: network → spool
2. **scan** — research discovery over already-acquired rows (offline primitives)
3. **evaluate** — outcomes vs scan, PIT-safe
4. **status** — capture health vs analysis health vs edge (always unvalidated)

## Collector (do not repeat the failure)

```text
WebSocket receive
    → bounded in-memory batch
    → RawCaptureSpool.append_batch (fsync file + dir)
    → ack

async, separate process:
    sealed segment replay
    → normalize
    → participant expansion
    → Parquet
    → analysis cursors
```

Rules from `docs/analysis/memecoin/RAW_CAPTURE_REDESIGN_20260906.md`:

- Ack means raw bytes survived, not that science is complete.
- One exclusive writer lock.
- Capacity failure is `INCOMPLETE`, never deletes evidence.
- Failed writer requires reconciliation before further acks.
- Replay does not read the active segment.
- Cursor advances only after durable downstream commit; crash before cursor ⇒ replay + dedupe.
- Capture lag and processing lag are different operational metrics.
- No Kafka/Redis in V1.
- Do not inspect holdout/outcomes as part of collector health.

Port `research/nave/raw_capture_spool.py` almost as-is (rename schema `rocket.raw-capture.v1`). Do **not** port `prospective_collection.py` as the live pipeline.

Dune remains an optional later research tool with the existing credit guard. Not a V1 production job.

---

# CLI/API

JSON is **default** (bot-first). `--human` for markdown. `--json` accepted as explicit alias.

```text
rocket status
rocket macro
rocket cava
rocket crypto scan
rocket crypto evaluate
rocket crypto missed
rocket portfolio review
rocket watch check
rocket ism
rocket disclosures
rocket shorts
rocket options scan
rocket options evaluate
rocket memecoin status
rocket memecoin collect
rocket memecoin scan
rocket memecoin evaluate
```

**17 commands.** Removed vs NAVE ~90.

Challenged/removed from the draft list:

- No `rocket research run` (that was the Discord gateway).
- No `rocket present` / `report`.
- No `rocket context` (`macro` + `cava` are the contexts).
- No `rocket crypto status` (use `rocket status`).
- No `portfolio candidates` (ISM is separate).
- No `shorts evaluate` CLI in V1 (library only until a human workflow needs it).
- `memecoin scan` kept as an **offline primitive**, not a live strategy job. Strategy exploration stays possible on these primitives.

Common flags:

```text
--decision-time ISO8601
--replay --fixture PATH
--state-dir PATH          # overrides ROCKET_HOME
--human
```

Workflow-specific:

```text
portfolio review --state PATH [--theses PATH] [--refresh-inventory]
watch check --watches PATH
crypto evaluate|missed --outcomes PATH [--scan-run RUN_ID]
memecoin scan --input PATH
memecoin collect --spool PATH
```

Missing required caller state is exit 1 with `CALLER_STATE_MISSING`, not a fake empty portfolio.

---

# Shared result type

One type. Not per-workflow models.

```text
run_id
workflow
mode                  LIVE | REPLAY
operational           { status, providers[] }
status                research status
decision_time
started_at
completed_at
evidence[]
warnings[]
payload
safety_boundary
```

### Research status (minimal)

```text
SETUP_FOUND
NO_SETUP
INSUFFICIENT_EVIDENCE
ACTION_REQUIRED
ERROR
```

`DATA_UNAVAILABLE` is **operational**, not research. NAVE mixed them; that mix is the bug.

`STRATEGY_NOT_VALIDATED` is **not** a sixth global status. Experimental surfaces put `strategy_state` in payload and use `INSUFFICIENT_EVIDENCE` (or `NO_SETUP` if the scan legitimately found nothing **and** providers were healthy). Rocket never emits `VALIDATED`.

`ACTION_REQUIRED` = watch event or portfolio row that needs a human look. Still not an order.

### Operational status

```text
HEALTHY
PARTIAL
UNAVAILABLE
ERROR
```

Each provider:

```text
name, status, retrieved_at, failure_kind?, coverage?
```

Illegal combinations (engine reject):

- operational `UNAVAILABLE` + research `NO_SETUP`
- operational `UNAVAILABLE` + research `SETUP_FOUND`
- research `SETUP_FOUND` with zero `ELIGIBLE` evidence

Legal:

- `HEALTHY` + `NO_SETUP`
- `PARTIAL` + `NO_SETUP` (evaluated subset)
- `PARTIAL` + `INSUFFICIENT_EVIDENCE`
- `HEALTHY` + `INSUFFICIENT_EVIDENCE` (shorts missing catalyst)

### Evidence

```text
source
reference
claim
kind                  FACT | INFERENCE | HYPOTHESIS | UNKNOWN
event_time
observed_at
available_at
retrieved_at
decision_time
availability          ELIGIBLE | LATE | UNKNOWN
provenance            PROVIDER_RESULT | USER_STATE | DOMAIN_RULE | TEST_FIXTURE | ...
```

`observed_at` vs `retrieved_at` vs `available_at` stay distinct (shorts/ISM lesson).

---

# Testing

NAVE did **not** implement a consistent architecture here (`TESTING.md` is journal/trading-shaped; invariants live in scattered files). Rocket does.

## Harness (required from PR1, forever)

One registration table. A workflow that is not registered cannot merge.

```text
tests/
  harness.py                 # WORKFLOWS registry + assert_research_result()
  conftest.py
  contract/                  # runs against EVERY registered workflow
    test_schema.py
    test_pit.py
    test_operational_vs_research.py
    test_safety_boundary.py
    test_json_cli.py
    test_no_runtime_paths.py
  workflows/                 # same layout per surface
    test_macro.py
    test_cava.py
    test_crypto.py
    test_portfolio.py
    test_watch.py
    test_ism.py
    test_disclosures.py
    test_shorts.py
    test_options.py
    test_memecoin.py
  providers/                 # recorded HTTP/RPC fixtures; protocol tests
  compare/                   # NAVE semantic diff during migration only
  fixtures/workflows/<name>/
    input.json
    expected.json            # scientific fields only
```

`assert_research_result(result)` always checks:

- schema / JSON round-trip
- `safety_boundary`
- PIT legality
- operational vs research illegal combinations
- `execution_enabled is false`
- replay did not load live context
- no Hermes/OpenClaw/Nanobot/Discord fields

Every workflow fixture test calls that helper, then asserts payload-specific science.

CI on every PR:

```text
pytest -q -m 'not integration'
```

must run contract + all registered workflow fixtures. `integration` (live providers) is opt-in. A new implementation that skips the harness fails CI.

Adding a workflow later: register in `harness.py`, add `fixtures/workflows/<name>/`, add `tests/workflows/test_<name>.py`. Same pattern, always.

## Invariants preserved from NAVE (rewrite onto the harness)

| Invariant | NAVE proof today |
|---|---|
| Missing `available_at` is UNKNOWN, not eligible | `tests/test_research_core.py` |
| `SETUP_FOUND` requires eligible evidence | same |
| `ERROR` requires warning | same |
| Macro independent of Cava; expiry fail-closed | `tests/test_quant_usefulness.py` |
| Holiday session clock | same |
| Partial watches evaluate | same |
| Private state age ≠ market missingness | same |
| COT is regime not alt signal | `tests/test_crypto_futures_research.py` |
| Funnel stages visible; no candidate without macro | same |
| Replay vs live clock split | crypto futures tests |
| Canonical identity, no symbol join, no PONS default | `tests/test_memecoin_identity_integrity.py` |
| Duplicate snapshot rejected | same |
| ISM identity STALE/CURRENT/UNPUBLISHED | `tests/test_provider_gate_closure.py` |
| Roundup must not pick 2022 body match | same |
| Rankings never sub-index lists | same |
| OGE/House empty ≠ failure | disclosures + gate tests |
| Shorts missing factor unknown; macro-only rejected | short research tests |
| Options cannot self-validate | options research tests |
| Spool fsync, exclusive writer, corrupt tail fail-closed | `tests/test_raw_capture_spool.py` |
| Inventory refresh does not sign, create positions, or overwrite theses | `portfolio_ledger` tests |
| Secrets come from process env, not `HERMES_HOME` | rewrite of the gated Supadata test |

## Additional engine rules

- exit code 0 on `NO_SETUP` with healthy providers
- caller-state-missing vs price-unavailable vs inventory-incomplete
- Cava cursor not advanced on transcript failure
- package grep: no `~/.hermes`, no `--channel-id`
- env aliases accepted; tests must not mutate the parent environment
- memecoin payload always `edge: NO_EDGE_VALIDATED`
- semantic compare vs NAVE during migration (ignore `run_id`, generation clocks, Discord)

No live Discord, no gateway, **no signing** tests. Read-only inventory tests **are** required.

---

# Complexity targets

Measured against NAVE main checkout **excluding `.worktrees`**.

| Metric | NAVE now | Rocket V1 target |
|---|---|---|
| Primary Python files | ~471 (research 53, trading 125, cli 20, options 39, scripts 83, tests 124, …) | ≤ 65 prod + tests (harness + registry included) |
| Production LOC (excl tests) | ~80k | ≤ 12,000 |
| CLI commands | ~90 | 17 |
| Typer groups | 16 | 1 app + ~10 sub-apps |
| Result types | many (`ResearchStatus`, `StrategyState`, `SurvivalStatus`, `OutcomeStatus`, `GateStatus`, payload strings…) | 1 result + 2 status families |
| PIT implementations | 1 contract + several ad-hoc parsers | 1 module, workflows must call it |
| State roots | `~/.nave`, `~/.hermes/state`, `~/.hermes/profiles/quant/*`, `nave/var`, `nave/data/*`, sqlite caches | `~/.rocket` + caller paths |
| Runtime path literals | `~/.hermes`, `HERMES_HOME` | **0** |
| Discord references in research | `quant_runner`, `orchestration`, hermes CLI | **0** |
| Languages | Python (+ TS web unused) | Python |
| Provider frameworks | mixed OpenBB/backend/trading | capability registry + toml, not a plugin bus |
| Crypto engines | ≥3 CLI entrypoints + analysis + theory_v2 | 1 |
| Memecoin hot path stores | SQLite firehose | spool JSONL |

If a PR would exceed these, it is the wrong PR.

---

# Incremental migration

Never two permanent production owners.

For **each** workflow, in order:

1. Implement Rocket workflow + tests.
2. Safe live comparison against NAVE: same `decision_time`, same fixtures/live window; semantic diff of scientific fields (status, funnel counts, evidence availability, provider health, candidate identities). Ignore `run_id`, Discord, generation clocks.
3. Runtime adapter switches the command (Agent script: `rocket … --json` then existing presenter).
4. Disable the old NAVE job/command for that workflow only.
5. Leave NAVE code in place until the next workflow is done; do not delete NAVE in lockstep.

Suggested cutover order (matches current enabled Quant jobs):

1. watch
2. cava
3. macro (new explicit command; currently implicit)
4. crypto scan
5. portfolio review
6. ism
7. disclosures
8. shorts
9. options (still unscheduled)
10. memecoin collect/primitives (still disabled as strategy)

Comparison harness lives in Rocket `tests/compare/` and may **import NAVE as a subprocess** during migration, then be deleted. It does not make Rocket depend on NAVE at runtime.

---

# Implementation phases

## Phase 0 — Skeleton + harness + tracking issues (PR1)

Repo `rocket/`. `pyproject.toml`. `models.py` + `pit.py` + operational validators. `store.py` run journal. `cli.py` with `status`. Capability registry + empty `providers.toml` / `env.toml`. **Test harness with contract suite** (even before real providers: a fixture workflow must pass `assert_research_result`). Config without home paths. No Hermes discovery.

On first commit / GitHub create, open the three tracking issues below (options strategy, memecoin strategy, crypto-futures polish). Do not implement those strategies in V1.

## Phase 1 — Providers + macro (PR2–PR3)

Register MacroSeries and Quotes. FRED/OpenBB, Yahoo, session clock. `rocket macro` on the harness. Cache parquet.

## Phase 2 — Daily Abi surfaces without crypto (PR4–PR6)

Cava (port pipeline, env secrets only). Watch. Portfolio review **including read-only Inventory provider** (port ledger logic, drop Hermes default). Each lands on the harness before the next.

## Phase 3 — Crypto (PR7–PR8)

Universe + Perps + COT capabilities. One engine. Live scan + replay + evaluate + missed. Harness + NAVE compare.

## Phase 4 — ISM, disclosures, shorts (PR9–PR11)

Same: implement → harness → compare. No Discord fields.

## Phase 5 — Options + memecoin primitives (PR12–PR13)

Options research contract (never auto-`VALIDATED`). Memecoin primitives + spool collector. Strategy **not** implemented. `edge: NO_EDGE_VALIDATED` asserted by harness.

## Phase 6 — Cutover (PR14)

Adapter scripts outside Rocket. Per-workflow switch. Disable NAVE owners one by one. Complexity budget + `rg` for runtime paths. Harness remains after compare/ is deleted.

Estimated calendar: 6 phases, ~14 PRs. Do not start Phase 6 for a workflow before its compare tests pass.

---

# Repository structure

Smallest layout. No extra ceremony.

```text
rocket/
  pyproject.toml
  README.md
  rocket/
    __init__.py
    cli.py
    models.py          # ResearchResult, Evidence, statuses
    pit.py             # the only PIT implementation
    store.py           # runs/ + contexts/ + state/
    config.py          # env + providers.toml; read-only env; no home-runtime paths
    providers/
      protocols.py     # Quotes, MacroSeries, Inventory, …
      registry.py      # toml-driven primary/fallbacks
      fred.py
      quotes.py
      hyperliquid.py
      coingecko.py
      cftc.py
      ism.py
      house.py
      oge.py
      fmp.py
      supadata.py
      inventory.py     # read-only Solana/ONDO
    workflows/
      macro.py
      cava.py
      crypto.py
      portfolio.py
      watch.py
      ism.py
      disclosures.py
      shorts.py
      options.py
      memecoin.py
    capture/
      spool.py         # port of RawCaptureSpool
  tests/
    harness.py
    contract/
    workflows/
    providers/
    fixtures/
    compare/           # migration-only
  config/
    providers.toml
    env.toml
  docs/
    ROCKET_PLAN.md
```

No `hermes/`, no `backend/`, no `web/`, no `ops/` cron, no `trading/`.

---

# Key decisions

1. **CLI+JSON, not HTTP.** Any bot presents the same result type. Daemons and MCP belong to runtimes.
2. **Two status families from day one.** Operational vs research. `DATA_UNAVAILABLE` leaves the research enum.
3. **Exit 0 on NO_SETUP.** Bots currently confuse emptiness with failure.
4. **Caller-owned theses/watches; wallet-backed inventory is read-only evidence.** Zero `~/.hermes` / `HERMES_HOME` in package.
5. **Env is consumed, never deleted.** Existing names (`FRED_API_KEY`, `FMP_API_KEY`, `SUPADATA_*`, `HELIUS_API_KEY`, …) stay. Aliases for `NAVE_*` during migration. No profile-file hunting.
6. **Providers are modular.** Capability protocol + toml registry + fallbacks. Not hardcoded vendors, not a plugin bus.
7. **Cava is overlay; macro is canonical.** Crypto/portfolio never require Cava.
8. **One crypto engine.** PR41/duplicate scanners stay dead.
9. **JSON default.** `--human` is the opt-in.
10. **Run journal is append-only.** Latest context snapshots are separate.
11. **Memecoin V1 is capture+primitives.** Strategy stays exploratory (`NO EDGE VALIDATED`). No fourth SQLite gate.
12. **Python only.** Polars/Parquet/DuckDB. pandas only at OpenBB edge.
13. **Adapters never enter this repo.**
14. **Per-workflow cutover with semantic diff.** No big bang, no dual permanent owners.
15. **Rocket never writes VALIDATED.**
16. **One test harness from PR1.** Every workflow and future PR uses the same contract helper and fixture layout.
17. **Unscheduled strategies get repo issues, not silence.** Options (stocks+crypto why-it-failed), memecoin (no edge), crypto-futures polish (top-100 scan is live; strategy still experimental).
18. **Live crypto universe is top 100 + liquid perps.** Not a discretionary coin list.

---

# Estimated reuse vs rewrite

Of **Rocket V1 code** (~10–12k LOC):

- **~25–35% ported** (contracts/PIT, macro, market clock, Cava pipeline, disclosure/OGE/House providers, short factors, watch evaluator, crypto funnel, identity, ISM identity/scraper, raw spool, memecoin primitives, read-only inventory ledger).
- **~65–75% rewritten** (CLI, store/journal, operational envelope, capability registry, provider I/O without Hermes, portfolio I/O, crypto live extract without trading package, collector wiring, test harness).

Of **NAVE volume** (~80k prod LOC + 90 commands + hermes/web/backend/scripts):

- **~90% dropped** (execution, signing/wallet CLIs, Discord, duplicate CLIs, options platform, experiment scripts, scheduler, Hermes integration, SQLite collector, presentation). Read-only inventory is **not** dropped.
- **~5–8% ported into Rocket.**
- Remainder is tests rewritten as specifications.

---

# Major complexity eliminated

- ~73 CLI commands
- Discord/Hermes/channel_id/Shabbat inside research
- Dual/triple crypto scanners and theory_v2/squeeze/capitulation
- Options gem/walkforward/visualization platform
- `quant_runner` subprocess + presentation + notification fingerprint
- Default `~/.hermes` portfolio/watch discovery
- SQLite as memecoin firehose
- Overwrite-only `results/{workflow}.json` as the journal
- Provider-failure vs NO_SETUP collapse
- Scheduler manifests in the research repo
- Web + FastAPI + MCP + wallet **signing** CLI (read-only inventory stays)
- Migration-only reports and worktree copies as if they were product

---

# Open questions (none blocking V1)

None that change the boundary. Defaults locked by this plan:

- Integration = CLI+JSON (not HTTP).
- Options unschedulable; memecoin **strategy** unschedulable; memecoin **primitives** exist. All three strategy follow-ups are GitHub issues at repo init.
- Short universe remains a small research set until a later explicit change.
- Dune is not a V1 default.
- Inventory V1 = Solana/ONDO read-only using existing env RPC; other chains are new provider rows later.

---

# Success bar

Rocket beats NAVE when:

- `rg 'hermes|discord|openclaw|nanobot' rocket/` is empty (except this plan’s historical notes in `docs/`).
- Command count ≤ 17.
- Prod LOC ≤ 12k.
- The **harness** runs on every PR; every registered workflow passes `assert_research_result` plus its fixture.
- Surfaces 1–11 actually acquire data and emit presentable JSON; memecoin strategy remains unvalidated.
- Each cut-over workflow has a passing semantic compare against NAVE, then a **single** enabled owner.
- Cava down does not disable `rocket crypto scan` or `rocket portfolio review`.
- `NO_SETUP` with healthy providers exits 0.
- Portfolio review can use read-only wallet inventory without signing or Hermes paths.
- Existing env var **names** still work; Rocket never deletes them.
- A new quotes/macro vendor can be added via toml + module without rewriting workflows.
- Memecoin collect can ack frames without SQLite/participants on the hot path.
- Repo has open issues for options (why stocks+crypto failed), memecoin strategy, and crypto-futures polish; live crypto scan is top-100.

---

# FINAL

**ROCKET_PLAN_READY**

| Item | Value |
|---|---|
| V1 feature count | **12** research surfaces + `status` (17 CLI commands) |
| Implementation phases | **6** (~14 PRs) |
| NAVE code reused vs rewritten | **~30% of Rocket is ported; ~70% rewritten; ~90% of NAVE volume dropped** |
| Major complexity eliminated | Discord/runtime coupling, ~73 commands, duplicate crypto engines, SQLite collector hot path, Hermes path defaults, mixed operational/research status, options platform, signing/execution (read-only inventory kept) |
