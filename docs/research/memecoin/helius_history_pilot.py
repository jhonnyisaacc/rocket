"""Bounded read-only history pilot: two requests maximum; reuse cached responses.

Reads the existing Helius MCP credential without printing or persisting it.
No automatic pagination or retries. Prints aggregate coverage, not PnL.
"""
import datetime
import json
import pathlib
import tomllib
import urllib.request
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "data" / "helius-pilot-2026-09-16"
WALLETS = {
    "fomo_unipcs_candidate": "2heJbC32Tpfcb3nbUb5ER61K11FGZVfVGtVnDm6LDogF",
    "historical_cohort_sample": "789sBYAGntSyAPoS4ZH3zo3SUFuv1jeAjPeaq7muVany",
}


def main():
    config = tomllib.loads(pathlib.Path("/Users/jhonny/.codex/config.toml").read_text())
    key = config["mcp_servers"]["helius"]["env"]["HELIUS_API_KEY"]
    OUT.mkdir(parents=True, exist_ok=True)
    summaries = []
    for label, address in WALLETS.items():
        target = OUT / (label + ".json")
        cached = target.exists()
        if cached:
            capture = json.loads(target.read_text())
        else:
            body = {"jsonrpc": "2.0", "id": label, "method": "getTransactionsForAddress",
                    "params": [address, {"transactionDetails": "full", "encoding": "jsonParsed",
                    "maxSupportedTransactionVersion": 0, "limit": 100, "sortOrder": "desc",
                    "filters": {"tokenAccounts": "balanceChanged"}}]}
            request = urllib.request.Request("https://mainnet.helius-rpc.com/?api-key=" + key,
                                             data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.load(response)
            except Exception as exc:
                # Do not expose exception messages: they can contain the credential URL.
                print(json.dumps({"label": label, "error_type": type(exc).__name__, "stopped": True}))
                return
            if "error" in payload:
                print(json.dumps({"label": label, "rpc_error_code": payload["error"].get("code"), "stopped": True}))
                return
            capture = {"retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       "address": address, "request": body, "response": payload,
                       "estimated_credits": 10, "complete_history": False}
            target.write_text(json.dumps(capture, indent=2) + "\n")
        result = capture["response"].get("result", {})
        rows = result.get("data", [])
        stamps = [r["blockTime"] for r in rows if r.get("blockTime") is not None]
        programs = Counter()
        token_rows = failed = owner_delta_rows = 0
        for row in rows:
            meta = row.get("meta") or {}
            failed += meta.get("err") is not None
            token_rows += bool(meta.get("preTokenBalances") or meta.get("postTokenBalances"))
            balances = {}
            for sign, field in ((-1, "preTokenBalances"), (1, "postTokenBalances")):
                for b in meta.get(field) or []:
                    if b.get("owner") == address:
                        mint = b["mint"]
                        balances[mint] = balances.get(mint, 0) + sign * int(b["uiTokenAmount"]["amount"])
            owner_delta_rows += any(balances.values())
            instructions = list(((row.get("transaction") or {}).get("message") or {}).get("instructions", []))
            instructions += [i for inner in meta.get("innerInstructions") or [] for i in inner.get("instructions", [])]
            programs.update(set(str(i.get("programId")) for i in instructions if i.get("programId")))
        summaries.append({"label": label, "cached": cached, "records": len(rows),
                          "estimated_new_credits": 0 if cached else 10,
                          "oldest_utc": datetime.datetime.fromtimestamp(min(stamps), datetime.timezone.utc).isoformat() if stamps else None,
                          "newest_utc": datetime.datetime.fromtimestamp(max(stamps), datetime.timezone.utc).isoformat() if stamps else None,
                          "has_more": bool(result.get("paginationToken")), "failed_transactions": failed,
                          "rows_with_token_balances": token_rows, "rows_with_owner_token_delta": owner_delta_rows,
                          "programs": programs.most_common(8)})
    report = {"edge": "NO_EDGE_VALIDATED", "summaries": summaries,
              "limitations": "Recent-page coverage audit only. Token deltas can be transfers; no PnL or swap classification yet."}
    (OUT / "coverage.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
