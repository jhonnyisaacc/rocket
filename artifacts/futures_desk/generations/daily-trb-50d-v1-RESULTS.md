# `daily-trb-50d-v1` results

Validation. One run of the frozen page `daily-trb-50d-v1.md`. No parameter was changed after this table. `execution_enabled` stays false. The live scan was not changed. No `ENTER_CONTRACT_v1`.

Retrieved 2026-09-23T12:23:54Z from `rocket.providers.hyperliquid.fetch_candles` (`candleSnapshot`, interval `1d` only) and public `fundingHistory` on the same HTTP client. No second candle client. No invented 1h price bars.

## Screening label

The PR #31 hourly `trb-50d` result is screening only. On the 6.845-month 1h tape that contract's overlapping net return was about +0.0131 at 20bps and +0.0111 at 40bps, funding included, R undefined. That clock was a 4h close and a 1h fill. It is not this validation and it is not mixed into the means below.

## Tape

Request 2025-09-23T00:00:00Z through 2026-09-23T12:23:54Z. BTC returned 366 daily bars, first open 2025-09-23T00:00:00Z, last open 2026-09-23T00:00:00Z. Completed BTC bars end at 2026-09-22T00:00:00Z. The last open is still forming and was not used as a signal or as channel history. BTC gaps in the returned series: 0.

Witness prices. BTC session opened 2026-06-25T00:00:00Z low 58062. HYPE session opened 2026-09-22T00:00:00Z high 97.816. June fills are counted from 2026-06-25T00:00:00Z through 2026-08-31T23:59:59Z. HYPE fills are counted from 2026-09-15T00:00:00Z through 2026-09-29T23:59:59Z, clipped to this tape (last open 2026-09-23T00:00:00Z).

## Universe

Eligibility is a point-in-time daily quote-volume floor computed from the daily bar: base volume times close on the signal day at least 5,000,000. That is the live scan's 24h quote-volume floor applied to the completed signal day, not today's dayNtlVlm, open interest, spread, or a backward-stamped top 100. Missing candles, a failed fetch_candles request, or fewer than 51 completed daily bars are exclusion. Delisted names are absent from metaAndAssetCtxs and were not reconstructed. fetch_candles uppercases the coin; a name the venue rejects in uppercase is a failed request.

Listed perps returned by `fetch_perp_markets`: 178. Candle request failed or empty: 6. Fewer than 51 completed daily bars: 2. Eligible names (at least 51 completed bars and at least one later bar with quote notional >= 5,000,000): 124.

Failed or empty candle requests: KPEPE (HTTPStatusError), KSHIB (HTTPStatusError), KBONK (HTTPStatusError), KLUNC (HTTPStatusError), KFLOKI (HTTPStatusError), KNEIRO (HTTPStatusError).

Breaks on a completed close through the prior 50 closes: 7566. Of those, 6282 were below the quote-volume floor and are not events. Eligible events: 1284. Unresolved fills: 0. Still open (fill known, tenth session not printed): 96.

## Event study

Equal-weighted overlapping events. This is the hypothesis. Closed funded events only. Open events and funding-incomplete events are out of the mean and out of the drawdown.

Closed funded events: 1188. Funding incomplete: 0. Still open: 96.

| | Events | Mean net return, 20bps + funding | Mean net return, 40bps + funding |
|---|---:|---:|---:|
| All | 1188 | -0.008253 | -0.010253 |
| Long | 616 | -0.023301 | -0.025301 |
| Short | 572 | 0.007953 | 0.005953 |

Gross mean before costs and funding: -0.007945. Mean funding drag (direction times the rate sum): -0.001692. A funding print is stamped about 50ms after the hour, so the print on the exit hour falls after the exit open and is outside `(fill, exit]`. Standard deviation of the 20bps event returns: 0.163906. Events overlap, so that deviation is not an independent-sample error.

Drawdown of summed unit-notional event returns, ordered by exit: -18.8468 at 20bps, -19.8708 at 40bps. Fraction of opened days in a position, averaged across the 124 eligible names: 12.7%.

### By calendar month of the fill

| Month | Events | Long | Short | Mean 20bps | Mean 40bps | Sum 20bps |
|---|---:|---:|---:|---:|---:|---:|
| 2025-11 | 128 | 9 | 119 | 0.003523 | 0.001523 | 0.450952 |
| 2025-12 | 93 | 13 | 80 | -0.007053 | -0.009053 | -0.655959 |
| 2026-01 | 99 | 55 | 44 | 0.007899 | 0.005899 | 0.782041 |
| 2026-02 | 123 | 9 | 114 | 0.007211 | 0.005211 | 0.886923 |
| 2026-03 | 49 | 28 | 21 | -0.021383 | -0.023383 | -1.047752 |
| 2026-04 | 83 | 63 | 20 | -0.022666 | -0.024666 | -1.881290 |
| 2026-05 | 163 | 142 | 21 | -0.004861 | -0.006861 | -0.792349 |
| 2026-06 | 137 | 26 | 111 | -0.066776 | -0.068776 | -9.148326 |
| 2026-07 | 54 | 33 | 21 | -0.000949 | -0.002949 | -0.051270 |
| 2026-08 | 180 | 161 | 19 | 0.026730 | 0.024730 | 4.811422 |
| 2026-09 | 79 | 77 | 2 | -0.039987 | -0.041987 | -3.158942 |

### By asset

Sorted by summed 20bps net return. Share is that sum divided by the event-study total.

| Coin | Events | Long | Short | Mean 20bps | Mean 40bps | Sum 20bps | Share of sum |
|---|---:|---:|---:|---:|---:|---:|---:|
| VVV | 41 | 37 | 4 | 0.073063 | 0.071063 | 2.995584 | -30.6% |
| NEAR | 24 | 15 | 9 | 0.064712 | 0.062712 | 1.553087 | -15.8% |
| LIT | 29 | 20 | 9 | 0.050557 | 0.048557 | 1.466141 | -15.0% |
| KAITO | 12 | 8 | 4 | 0.120779 | 0.118779 | 1.449352 | -14.8% |
| ETH | 33 | 10 | 23 | 0.033772 | 0.031772 | 1.114479 | -11.4% |
| UNI | 24 | 16 | 8 | 0.040044 | 0.038044 | 0.961053 | -9.8% |
| ENA | 39 | 11 | 28 | 0.024613 | 0.022613 | 0.959919 | -9.8% |
| SOL | 39 | 14 | 25 | 0.021218 | 0.019218 | 0.827498 | -8.4% |
| LINK | 32 | 12 | 20 | 0.024477 | 0.022477 | 0.783278 | -8.0% |
| ACE | 2 | 2 | 0 | 0.378059 | 0.376059 | 0.756117 | -7.7% |
| MON | 25 | 14 | 11 | 0.025138 | 0.023138 | 0.628443 | -6.4% |
| APT | 4 | 0 | 4 | 0.129368 | 0.127368 | 0.517470 | -5.3% |
| ZEC | 30 | 23 | 7 | 0.015816 | 0.013816 | 0.474484 | -4.8% |
| ARB | 23 | 12 | 11 | 0.019942 | 0.017942 | 0.458660 | -4.7% |
| MEGA | 3 | 0 | 3 | 0.149483 | 0.147483 | 0.448448 | -4.6% |
| TIA | 3 | 0 | 3 | 0.147917 | 0.145917 | 0.443750 | -4.5% |
| HYPE | 43 | 31 | 12 | 0.009620 | 0.007620 | 0.413642 | -4.2% |
| XMR | 27 | 20 | 7 | 0.014560 | 0.012560 | 0.393126 | -4.0% |
| BTC | 42 | 19 | 23 | 0.008969 | 0.006969 | 0.376699 | -3.8% |
| WLD | 22 | 8 | 14 | 0.014303 | 0.012303 | 0.314672 | -3.2% |
| POPCAT | 1 | 0 | 1 | 0.254730 | 0.252730 | 0.254730 | -2.6% |
| SUI | 39 | 7 | 32 | 0.006497 | 0.004497 | 0.253377 | -2.6% |
| PUMP | 36 | 17 | 19 | 0.005695 | 0.003695 | 0.205008 | -2.1% |
| BNB | 40 | 20 | 20 | 0.004626 | 0.002626 | 0.185032 | -1.9% |
| CHIP | 5 | 5 | 0 | 0.033233 | 0.031233 | 0.166165 | -1.7% |
| BIO | 6 | 6 | 0 | 0.025001 | 0.023001 | 0.150009 | -1.5% |
| OP | 2 | 0 | 2 | 0.068812 | 0.066812 | 0.137623 | -1.4% |
| PENDLE | 9 | 8 | 1 | 0.010668 | 0.008668 | 0.096010 | -1.0% |
| AVAX | 27 | 5 | 22 | 0.002986 | 0.000986 | 0.080629 | -0.8% |
| ONDO | 6 | 6 | 0 | 0.011421 | 0.009421 | 0.068525 | -0.7% |
| YGG | 1 | 0 | 1 | 0.064667 | 0.062667 | 0.064667 | -0.7% |
| ETHFI | 9 | 9 | 0 | 0.002561 | 0.000561 | 0.023049 | -0.2% |
| CELO | 1 | 0 | 1 | 0.021642 | 0.019642 | 0.021642 | -0.2% |
| LTC | 17 | 5 | 12 | 0.001090 | -0.000910 | 0.018529 | -0.2% |
| MELANIA | 1 | 1 | 0 | 0.004288 | 0.002288 | 0.004288 | -0.0% |
| GRAM | 1 | 0 | 1 | -0.033045 | -0.035045 | -0.033045 | 0.3% |
| PAXG | 30 | 20 | 10 | -0.001349 | -0.003349 | -0.040461 | 0.4% |
| MERL | 1 | 1 | 0 | -0.046754 | -0.048754 | -0.046754 | 0.5% |
| MORPHO | 2 | 2 | 0 | -0.025911 | -0.027911 | -0.051823 | 0.5% |
| CRV | 16 | 8 | 8 | -0.004818 | -0.006818 | -0.077085 | 0.8% |
| SKR | 2 | 2 | 0 | -0.042282 | -0.044282 | -0.084565 | 0.9% |
| APE | 1 | 1 | 0 | -0.087468 | -0.089468 | -0.087468 | 0.9% |
| ADA | 25 | 4 | 21 | -0.003565 | -0.005565 | -0.089135 | 0.9% |
| WLFI | 10 | 2 | 8 | -0.010150 | -0.012150 | -0.101504 | 1.0% |
| BCH | 13 | 5 | 8 | -0.007847 | -0.009847 | -0.102008 | 1.0% |
| TRUMP | 9 | 4 | 5 | -0.011901 | -0.013901 | -0.107110 | 1.1% |
| ALGO | 3 | 3 | 0 | -0.036323 | -0.038323 | -0.108968 | 1.1% |
| SPX | 4 | 3 | 1 | -0.028318 | -0.030318 | -0.113272 | 1.2% |
| MET | 1 | 1 | 0 | -0.115184 | -0.117184 | -0.115184 | 1.2% |
| ZORA | 1 | 1 | 0 | -0.115814 | -0.117814 | -0.115814 | 1.2% |
| LDO | 1 | 1 | 0 | -0.131231 | -0.133231 | -0.131231 | 1.3% |
| AERO | 3 | 3 | 0 | -0.045825 | -0.047825 | -0.137475 | 1.4% |
| BLUR | 1 | 1 | 0 | -0.150458 | -0.152458 | -0.150458 | 1.5% |
| HEMI | 2 | 2 | 0 | -0.080992 | -0.082992 | -0.161985 | 1.7% |
| TNSR | 1 | 1 | 0 | -0.163809 | -0.165809 | -0.163809 | 1.7% |
| DOT | 3 | 3 | 0 | -0.062439 | -0.064439 | -0.187317 | 1.9% |
| DOGE | 36 | 11 | 25 | -0.005315 | -0.007315 | -0.191349 | 2.0% |
| TRX | 7 | 3 | 4 | -0.027524 | -0.029524 | -0.192669 | 2.0% |
| PENGU | 16 | 11 | 5 | -0.013021 | -0.015021 | -0.208333 | 2.1% |
| AZTEC | 1 | 1 | 0 | -0.208943 | -0.210943 | -0.208943 | 2.1% |
| LAYER | 1 | 1 | 0 | -0.235406 | -0.237406 | -0.235406 | 2.4% |
| PNUT | 1 | 1 | 0 | -0.243274 | -0.245274 | -0.243274 | 2.5% |
| WIF | 6 | 2 | 4 | -0.041048 | -0.043048 | -0.246286 | 2.5% |
| SOPH | 1 | 1 | 0 | -0.274431 | -0.276431 | -0.274431 | 2.8% |
| ANIME | 2 | 2 | 0 | -0.137251 | -0.139251 | -0.274502 | 2.8% |
| PROVE | 1 | 1 | 0 | -0.276939 | -0.278939 | -0.276939 | 2.8% |
| AXS | 5 | 5 | 0 | -0.063674 | -0.065674 | -0.318372 | 3.2% |
| BOME | 2 | 2 | 0 | -0.179941 | -0.181941 | -0.359882 | 3.7% |
| ICP | 2 | 2 | 0 | -0.180668 | -0.182668 | -0.361337 | 3.7% |
| AAVE | 33 | 7 | 26 | -0.011715 | -0.013715 | -0.386599 | 3.9% |
| CC | 4 | 4 | 0 | -0.098439 | -0.100439 | -0.393755 | 4.0% |
| POL | 2 | 2 | 0 | -0.197573 | -0.199573 | -0.395147 | 4.0% |
| RENDER | 2 | 2 | 0 | -0.208048 | -0.210048 | -0.416096 | 4.2% |
| 0G | 1 | 1 | 0 | -0.416971 | -0.418971 | -0.416971 | 4.3% |
| HMSTR | 1 | 1 | 0 | -0.428249 | -0.430249 | -0.428249 | 4.4% |
| ORDI | 1 | 1 | 0 | -0.467853 | -0.469853 | -0.467853 | 4.8% |
| NIL | 1 | 1 | 0 | -0.484954 | -0.486954 | -0.484954 | 4.9% |
| XLM | 3 | 3 | 0 | -0.167198 | -0.169198 | -0.501594 | 5.1% |
| INIT | 2 | 2 | 0 | -0.261384 | -0.263384 | -0.522767 | 5.3% |
| GRASS | 2 | 2 | 0 | -0.279426 | -0.281426 | -0.558852 | 5.7% |
| INJ | 10 | 10 | 0 | -0.056289 | -0.058289 | -0.562893 | 5.7% |
| FET | 5 | 5 | 0 | -0.114678 | -0.116678 | -0.573389 | 5.8% |
| XPL | 33 | 6 | 27 | -0.020368 | -0.022368 | -0.672143 | 6.9% |
| ZRO | 15 | 10 | 5 | -0.045889 | -0.047889 | -0.688332 | 7.0% |
| STABLE | 4 | 4 | 0 | -0.177937 | -0.179937 | -0.711748 | 7.3% |
| TAO | 23 | 11 | 12 | -0.031493 | -0.033493 | -0.724332 | 7.4% |
| EIGEN | 3 | 3 | 0 | -0.255146 | -0.257146 | -0.765438 | 7.8% |
| PURR | 6 | 6 | 0 | -0.133385 | -0.135385 | -0.800311 | 8.2% |
| VIRTUAL | 5 | 4 | 1 | -0.167068 | -0.169068 | -0.835338 | 8.5% |
| JTO | 7 | 7 | 0 | -0.119850 | -0.121850 | -0.838948 | 8.6% |
| CASHCAT | 2 | 2 | 0 | -0.434511 | -0.436511 | -0.869022 | 8.9% |
| RESOLV | 6 | 5 | 1 | -0.145128 | -0.147128 | -0.870768 | 8.9% |
| JUP | 9 | 7 | 2 | -0.103218 | -0.105218 | -0.928966 | 9.5% |
| DASH | 6 | 6 | 0 | -0.180315 | -0.182315 | -1.081890 | 11.0% |
| STRK | 4 | 4 | 0 | -0.333980 | -0.335980 | -1.335920 | 13.6% |
| ASTER | 23 | 12 | 11 | -0.078747 | -0.080747 | -1.811177 | 18.5% |
| FARTCOIN | 26 | 9 | 17 | -0.076147 | -0.078147 | -1.979815 | 20.2% |
| XRP | 41 | 7 | 34 | -0.054836 | -0.056836 | -2.248278 | 22.9% |

### Concentration

Shares use the summed 20bps net return of closed funded events. They do not remove trades from the mean above.

Largest coin by summed net return: VVV. Sum 2.995584. Share -30.6%. Complement events 1147, complement mean -0.011160. Same coin's share at 40bps: -23.9%.

June 2026 rebound window, all names, fills 2026-06-25 through 2026-08-31: 257 closed funded events, sum 2.919017, share -29.8%. Complement events 931, complement mean -0.013667.

HYPE high window, HYPE fills from 2026-09-15 through seven days after 2026-09-22, clipped to the tape: 0 closed funded events, sum 0.000000, share -0.0%. Complement events 1188, complement mean -0.008253. Open HYPE events in that window (not in the mean): 4.

## Per-name book

Portfolio construction. A new signal in a name is skipped while that name's prior 10-session window is still open. This section is not the event-study mean and is not a claim the signal improved.

Taken fills: 488. Skipped because the prior window was open: 796. Closed funded: 448. Funding incomplete: 0. Still open: 40.

| | Trades | Mean net return, 20bps + funding | Mean net return, 40bps + funding |
|---|---:|---:|---:|
| All | 448 | -0.002839 | -0.004839 |
| Long | 240 | -0.023469 | -0.025469 |
| Short | 208 | 0.020965 | 0.018965 |

Drawdown of summed unit-notional book returns, ordered by exit: -6.7220 at 20bps, -7.1300 at 40bps. Fraction of opened days in a position, same eligible-name average: 10.5%.

### By calendar month of the fill

| Month | Trades | Long | Short | Mean 20bps | Mean 40bps | Sum 20bps |
|---|---:|---:|---:|---:|---:|---:|
| 2025-11 | 38 | 5 | 33 | 0.039768 | 0.037768 | 1.511202 |
| 2025-12 | 40 | 6 | 34 | -0.008105 | -0.010105 | -0.324209 |
| 2026-01 | 49 | 25 | 24 | 0.016025 | 0.014025 | 0.785209 |
| 2026-02 | 38 | 5 | 33 | -0.012347 | -0.014347 | -0.469192 |
| 2026-03 | 18 | 9 | 9 | -0.020301 | -0.022301 | -0.365417 |
| 2026-04 | 41 | 30 | 11 | -0.023387 | -0.025387 | -0.958857 |
| 2026-05 | 66 | 53 | 13 | 0.001773 | -0.000227 | 0.117038 |
| 2026-06 | 45 | 11 | 34 | -0.071274 | -0.073274 | -3.207329 |
| 2026-07 | 20 | 13 | 7 | -0.029962 | -0.031962 | -0.599233 |
| 2026-08 | 62 | 54 | 8 | 0.056175 | 0.054175 | 3.482868 |
| 2026-09 | 31 | 29 | 2 | -0.040124 | -0.042124 | -1.243837 |

## Reading

The event-study mean net return is not positive at 20bps, so the daily break does not survive costs. The same mean is not positive at 40bps. The frozen concentration tests do not decide this result, because there is no positive mean for one coin or one episode to explain.

Experiments 2 and 3 were not run. 50, 10, the absent band, and the costs were not changed. No filter was added.

Hypothesis rejected
