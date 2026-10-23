---
name: rocket-x402-services
description: Judgement for paying x402 services through Rocket. It covers cost before spending and partial success. Use when a task needs a paid API or an endpoint returns HTTP 402.
license: MIT
---

# Paying for services, without surprising the user

Rocket holds no x402 catalogue today. This skill is the judgement to apply before any x402 spend goes through the wallet, and it blocks the spend until a priced route exists.

## Cost before spending

An x402 call spends real money per request. Tell the user the cost before paying. Say it before a loop. Checking five sources can mean five payments. Quote the dollar figure the service returns. Never convert an atomic amount by hand.

## A failing listing is usually the listing

Catalogues carry dead and non-compliant entries. When one fails, try a different service. A retry pays again for the same failure.

## Partial success is a real outcome

A payment can land while the fetch fails. Inspect both the payment and the resource before you report. Do not retry blindly. The retry may pay a second time.
