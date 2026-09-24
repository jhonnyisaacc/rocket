# Focused literature checks

Three primary papers only. Source bytes and SHA-256 provenance are archived in `sources/`. Discovery used the research-papers skill and Firecrawl semantic search; primary bodies were read directly. Search metadata called the first paper MELT, while the pinned v1 body calls it MemeTrans: this review uses the actual v1, not mixed-version claims.

1. [Hu et al., MemeTrans, arXiv:2602.13480v1](https://arxiv.org/html/2602.13480v1), preprint, §4.3–4.4. Bundle and fund-flow features motivate a related-wallet sensitivity and explicit separation of transfers from purchases. This study uses direct observed transfers as dependence flags, never proof of common ownership. Its dataset selects successfully migrated launches; its reported risk results cannot be imported into our all-launch sample. Our features must be trailing-only. Shared exchanges, routers and fee payers are insufficient ownership evidence.

2. [Mongardini et al., A Midsummer Meme’s Dream, arXiv:2507.01963v1](https://arxiv.org/html/2507.01963v1), pinned preprint version, §5.2–5.3. Repeated round trips and shallow-liquidity price inflation motivate net-acquisition checks, ordinary-buyer controls and rejecting peak-price returns. Similar buy/sell amounts alone do not prove manipulation: market makers also turn inventory over. Daily OHLCV screening thresholds are not transferred into our second-level triggers. The paper’s illustrative liquidity arithmetic is not used as a quote engine; protocol sources and actual account movements govern execution.

3. [Bailey et al., The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf), author-hosted paper, §2 and §5. Strategy selection on in-sample results can invert out-of-sample rankings. Concrete protections here: freeze hypotheses and shortlist rules, retain all failures, lock implementation before holdout access, and disclose all sensitivity scenarios. Twenty-four launches are not enough to estimate a reliable probability of overfitting or statistical significance; no such statistic is claimed.

No paper establishes a profitable wallet-copying strategy for this sample.
