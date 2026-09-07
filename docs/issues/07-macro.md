# Job: `rocket macro`

One issue for this job only. Canonical US rates/liquidity. Independent of Cava.

## Mental model

Context for other jobs, not a trade. `HEALTHY` + `NO_SETUP` means the book is current.

```
FRED (OpenBB if present, else public CSV) → EFFR, TGA, RRP, WALCL → regime + net liquidity
```

## Filters

- Each series needs a print ≥28 days before the latest or status is `INSUFFICIENT` (no fake `change_4w = 0`)
- Freshness: EFFR/RRP 5d, TGA/WALCL 10d
- Usable only if contract `current_macro_v1`, status `OK`, not expired (6h)

## Live output — 2026-09-07T17:35:46Z (`main` @ `2eaa8e9`)

`operational=HEALTHY` `research=NO_SETUP` contract OK regime **neutral**

| Factor | Value | 4w change | Status | Observation |
|---|---:|---:|---|---|
| EFFR | 3.63 | 0.0 | OK | 2026-09-03 |
| WDTGAL (TGA) | 944,364 | +15,039 | OK | 2026-09-02 |
| RRPONTSYD | 0.675 | −0.775 | OK | 2026-09-04 |
| WALCL | 6,737,204 | −11,363 | OK | 2026-09-02 |

Net liquidity (WALCL − TGA − RRP×1000): **5,792,165** (million USD).

## Review / polish

- [ ] One line: HEALTHY / NO_SETUP / regime / net liquidity so empty is not “macro broken”
- [ ] 4w direction in words next to the number (unchanged / falling / rising)
- [ ] Units labeled on net liquidity

Contract: JSON `ResearchResult`. Operational ≠ research. `execution_enabled` false.
