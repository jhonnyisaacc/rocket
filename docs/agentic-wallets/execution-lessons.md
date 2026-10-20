# Handle safety and fast execution

Apply these rules to every provider on this guide. Facts on this page are as of Oct 2026.

Rocket does not run these rules. They belong to the separate process that is allowed to sign.

## Refuse spam and look-alike tokens

Airdropped spam tokens show up in an EVM wallet. Do not interact with them. Do not approve them. Do not sell them.

Do not swap into a token that only reuses a name you already trust on another chain. Match the contract or mint from the quote. A shared ticker is not identification.

## Quote before you send

Get a quote first. Read the price impact and the slippage. Send the swap only after both are inside the limits below.

Keep quoted price impact under 1 percent. Set slippage from 1 percent to 2 percent. Do not set slippage above 3 percent. Check that the pool can hold the size. Abort when the price is already 5 percent to 10 percent past the entry you are mirroring.

## Run execution outside the chat loop

A webhook can land about 4 seconds to 5 seconds after a trade. One example is a Helius enhanced webhook. A chat-model loop then adds about 1 minute to 3 minutes. That delay is too slow for a scalp.

Put execution in an always-on service. The webhook calls the swap directly, under rules you approved before the event.

## Classify the tracked trade

Classify buy or sell from the tracked wallet's net change. Treat SOL, wSOL, USDC, and USDT as quote assets.

Count the trade only when the tracked wallet signs it. Many platforms add a shared fee-payer co-signer and a dust referral transfer. Filter those routers and programs out.

Open the signature in an explorer and read the signer there. An address field inside an app can name a different account.

## Mirror size and drop noise

On a partial sell, mirror the fraction of the trader's position at that event. Use the position the event reports. Do not reuse an older size.

Ignore a bridge. The fill you can copy is on the other chain, and the bridge can still refund.

Skip a signature you have already handled. Skip a failed transaction.

Repeated fixed amounts are often a quick-buy button in a user interface. Ignore a repeat below the minimum size you set.

## Follow the safety rules

Do not raise slippage to force a fill. Do not disable the price-impact check to catch a fast move.

If the quote fails any rule on this page, do not send the transaction. Wait for the next event.
