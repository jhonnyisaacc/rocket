# Wallet-cohort continuation protocol v0.2

Revised 2026-09-16 after checking the current paper revision and auditing the
released archive. See `2026-09-16-source-audit-and-wallet-pilot.md` for evidence.

Research only. This protocol does not generate a live trade signal, copy a
wallet, interact with a wallet, or establish an edge.

## Research question

At a fixed, public-data decision time, does the arrival of a *pre-qualified
early-wallet cohort*, combined with independently measured participation and
an integrity gate, improve the distribution of executable short-horizon
returns relative to matched eligible launches?

`Early-wallet cohort` is deliberately not synonymous with `insider`. The
dataset may describe observable timing and repeated co-occurrence, but must
not infer private information or a common controller without evidence.

## The unit of research

One row is an immutable `token × decision_time` snapshot. The row is eligible
only if every input was available at or before `decision_time`; the chain and
mint are canonical; and the observed pool supports a defined capacity test.
The evaluation horizons are 5m, 15m, 1h, 6h and 24h. Each records executable
return after fees and estimated price impact, maximum adverse/favourable
excursion, liquidity impairment, and stale/unexecutable status.

The entry event is a sequence, not a price threshold:

```text
DISCOVERED → IDENTITY_CONFIRMED → INTEGRITY_PASS → COHORT_OBSERVED
          → INDEPENDENT_DEMAND_CONFIRMED → RESEARCH_TRIGGERED → EXPIRED/LABELED
```

No row may move backward through this state machine after outcomes are known.

## Public identity map

Fomo and X usernames are labels, not addresses. A username-to-address mapping
is admissible only with an evidence record:

| Field | Requirement |
| --- | --- |
| `username`, `platform` | Exact public label and source URL |
| `chain`, `address` | Canonical chain/address pair |
| `mapping_method` | Public profile disclosure, signed proof, explicit public post, or UI association |
| `evidence_url`, `retrieved_at` | Immutable source and retrieval time |
| `confidence` | `high`, `medium`, or `low`, with rationale |
| `valid_from`, `valid_to` | Mapping interval; addresses may rotate |
| `cluster_id` | Optional; separate from a claimed human identity |

Screenshots, inferred position feeds, matching aliases, and a similar trade are
not sufficient on their own. A low-confidence map may support exploratory
clustering but cannot qualify a wallet for a trigger.

## Wallet and cohort qualification

Qualification uses a training period that ends before the evaluation period.
It is frozen before each test block; a wallet cannot be admitted because of a
future successful token.

The wallet panel stores both positive and negative behaviour:

- token-level, equal-weighted realised/executable outcomes; median outcome,
  hit rate, drawdown, holding time, and capacity;
- entry rank and delay from launch, buy size relative to liquidity, and
  position persistence rather than merely first-buy status;
- participation diversity by launchpad, creator cluster, narrative, and Fomo
  clan, plus leave-one-clan-out results;
- penalties for creator/funding/bundle linkage, atomic round trips, wash-like
  activity, immediate post-promotion dumping, and repeatedly unexecutable
  liquidity.

A cohort is a recurrent, time-decayed co-occurrence relationship—not just a
list of individually profitable wallets. Its event score must expose: number
of qualified members observed, first-buy rank, arrival-window density,
notional relative to liquidity, member persistence, and prior cohort outcome
without the current token. The cohort wallets are excluded from the
independent-buyer and independent-inflow features.

## Candidate trigger to test

This is a draft hypothesis, not yet a complete preregistration. Thresholds are
chosen only from a preceding training block and then frozen for the next block.

1. A canonical token/pool is observed with all point-in-time clocks present.
2. The integrity gate passes: no high-confidence creator/bundle domination,
   critical coordinated-sell or wash flag, unresolved copycat identity, or
   disqualifying liquidity/capacity condition.
3. A pre-qualified cohort has at least the learned minimum number of members
   entering in the learned time window. Its total size is material relative to
   displayed and executable liquidity, and its positions persist beyond the
   learned minimum duration.
4. Non-cohort buyer breadth and base-asset inflow accelerate in consecutive
   windows; the trigger cannot be satisfied by the cohort alone.
5. The price holds the post-event reference and no cohort sell, coordinated
   transfer-to-dumper, concentration breach, or data-staleness event occurs.

The companion exit study evaluates first-occurrence exits: integrity breach;
cohort net-sell/transfer-to-dumper; independent-flow reversal; liquidity
collapse; fixed adverse excursion; time expiry; and a data-freshness failure.
Select profit targets, trailing stops, and time limits using training and
validation only. Freeze the complete policy before opening the final holdout;
do not select an exit by comparing its holdout results.

## Controls that can falsify the idea

The cohort signal must beat all of the following at the same decision times
and with the same costs/capacity assumptions:

1. random eligible launches;
2. liquidity/volume/momentum-only candidates;
3. equally active, randomly assembled wallet groups;
4. symmetric randomization controls that preserve wallet activity and token
   popularity, with identical outcome exclusions in treatment and control;
5. the same cohort tested in shifted/random launch windows;
6. a no-trade baseline.

Use chronological, purged train/validation/test windows. Report outcomes by
token and by wallet, then remove the best one and best three outcomes. Repeat
by regime, launchpad, creator cluster, Fomo clan, and data-source availability.
Concentration in a slice limits the scope of the claim. A narrow regime can
support a narrow hypothesis only if that regime was defined before the test;
post-hoc slice selection cannot rescue a failed test.

## Promotion bar

The paper's v3 activity-matched placebo is a biased estimator and must not be
used as a null benchmark. A replacement randomization procedure needs its own
calibration on simulated no-signal data before it can supply a p-value.
Connected components indicate behavioral links, not independent people or
common ownership. Count distinct addresses separately from buyer rows.

The hypothesis remains `NO_EDGE_VALIDATED` unless a locked holdout has:

- positive costed expected return with uncertainty estimated by day/token
  clusters and a prespecified bounded left tail; report the median but do not
  require it to be positive for a strategy intentionally seeking rare large wins;
- better precision at a fixed alert budget than every preregistered control;
- sufficient executable liquidity for the defined small notional;
- stable results after top-outlier, clan, creator-cluster, and ecosystem
  exclusions (report top-outlier sensitivity without automatically discarding
  a legitimately positively skewed strategy); and
- a documented latency budget from event time to source availability to
  decision time.

The initial deliverable, if that bar is met, is a paper-trading research board
with explicit invalidation reasons. It is not autonomous execution.

## Why the protocol is strict

The current v3 reports adjusted outside-buyer lift of 16.1%, but SOL-inflow
lift of 6.3% has a 95% interval spanning zero. Its activity-matched placebo is
explicitly retained as a bias diagnostic, not a valid null. Neither outcome is
a tradable return. [Kamat, v3](https://arxiv.org/abs/2607.02795v3)

Large-scale Pump.fun work also reports wash trading, creator-address
obfuscation, coordinated sells, copycats, and social manipulation. This is
why the integrity gate precedes continuation testing rather than being a
decorative risk score. [Szwajcok et al., *Meme Coin Factories*](https://arxiv.org/abs/2609.10246)

Bundle-adjusted ownership is equally important: MELT reports that apparent
independent ownership can be substantially overstated when coordinated
accounts are not grouped. [MELT](https://arxiv.org/abs/2602.13480)
