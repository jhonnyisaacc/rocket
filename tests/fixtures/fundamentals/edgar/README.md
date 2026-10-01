# Offline SEC companyfacts recordings

These are reduced public SEC XBRL companyfacts recordings, downloaded from public
fixture repositories on 2026-10-01 because SEC's Akamai edge returned HTTP 403 to
this development environment. Only the adapter's supported concepts are retained;
individual fact values, dates, forms, units and accessions are unchanged.

- CAT: [open-finance-mcp facts_CAT.json](https://github.com/nathanaelhub/open-finance-mcp/blob/main/tests/fixtures/facts_CAT.json)
- JPM and MSFT: [finava SEC fixtures](https://github.com/LBB2005/finava/tree/main/src/lib/__fixtures__/sec), whose README identifies the source as SEC companyfacts fetched 2026-09-15.
- WMT: [CopeTech-Edgar WMT recording](https://github.com/pattty847/CopeTech-Edgar/blob/main/tests/fixtures/sec/companyfacts/wmt/companyfacts.json).
  This is deliberately partial: a January year end and a July quarter, without
  the prior-year quarterly EPS necessary for growth. It tests UNKNOWN coverage.

Official source URLs use `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`:
CAT 0000018230, JPM 0000019617, WMT 0000104169, MSFT 0000789019.
`company_tickers.json` is a small deterministic lookup containing those identities.

Tests mutate copies explicitly for restatements, future filings, missing units,
zero denominators and bearish EPS. No test reaches SEC over the network.
