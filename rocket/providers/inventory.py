"""Read-only Solana/ONDO inventory. Never signs. Never creates positions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit

import httpx

from rocket.config import env
from rocket.models import OperationalStatus
from rocket.providers.protocols import ProviderResult

# Officially mapped ONDO mints. Unknown *ondo mints stay pending_review.
KNOWN_ONDO = {
    "14Tqdo8V1FhzKsE3W2pFsZCzYPQxxupXRcqw9jv6ondo": ("AMZNON", "AMZN"),
    "fDxs5y12E7x7jBwCKBXGqt71uJmCWsAQ3Srkte6ondo": ("METAON", "META"),
    "FRmH6iRkMr33DLG6zVLR7EM4LojBFAuq6NtFzG6ondo": ("MSFTON", "MSFT"),
    "Wk8gC6iTNp8dqd4ghkJ3h1giiUnyhykwHh7tYWjondo": ("BACON", "BAC"),
    "6btaz134wjHkR8sqhAYrtSM6tavftfxnRvnyMd8ondo": ("COSTON", "COST"),
    "CY8ttw5rYCT6fFBJwqXofefqa7Ji9E8zfLmhRLmondo": ("FCXON", "FCX"),
    "KeGv7bsfR4MheC1CkmnAVceoApjrkvBhHYjWb67ondo": ("TSLAON", "TSLA"),
    "k18WJUULWheRkSpSquYGdNNmtuE2Vbw1hpuUi92ondo": ("SPYon", "SPY"),
}


class FileInventory:
    def __init__(self, records: tuple[Mapping[str, Any], ...] = ()):
        self.records = records

    def fetch(self, *, address: str, now: datetime | None = None) -> ProviderResult:
        del address
        return ProviderResult(
            status=OperationalStatus.HEALTHY,
            records=self.records,
            retrieved_at=now or datetime.now(UTC),
            source="caller.inventory",
        )


TOKEN_PROGRAMS = ("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                  "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
PUBLIC_RPCS = ("https://api.mainnet-beta.solana.com", "https://solana-rpc.publicnode.com")
MAINNET_GENESIS = "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d"


def rpc_order():
    urls = [env("SOLANA_RPC_URL")]
    key = env("HELIUS_API_KEY")
    if key:
        urls.append(f"https://mainnet.helius-rpc.com/?api-key={key}")
    return list(dict.fromkeys(url for url in [*urls, *PUBLIC_RPCS] if url))


def parse_accounts(rows, *, program, address, registry):
    """Integer raw amounts, not nullable uiAmount. Preserve every malformed account."""
    balances, errors, seen = {}, [], set()
    if not isinstance(rows, list):
        raise ValueError("token accounts must be an array")
    for index, row in enumerate(rows):
        try:
            account_id = row["pubkey"]
            account = row["account"]
            info = account["data"]["parsed"]["info"]
            mint = info["mint"]
            if account["owner"] != program or info["owner"] != address or account_id in seen:
                raise ValueError("account identity mismatch or duplicate")
            seen.add(account_id)
            raw, decimals = info["tokenAmount"]["amount"], info["tokenAmount"]["decimals"]
            if not isinstance(raw, str) or not raw.isdigit() or int(raw) > 2**64 - 1 or not isinstance(decimals, int) or isinstance(decimals, bool) or not 0 <= decimals <= 255:
                raise ValueError("malformed amount")
            if not isinstance(mint, str) or not mint:
                raise ValueError("missing mint")
            item = balances.setdefault(mint, {"mint": mint, "raw_amount": 0, "decimals": decimals,
                                              "token_program": program, "token_accounts": []})
            if item["decimals"] != decimals:
                raise ValueError("mint decimals disagree")
            item["raw_amount"] += int(raw)
            item["token_accounts"].append(account_id)
        except (KeyError, TypeError, ValueError):
            errors.append({"account_index": index, "token_program": program, "failure_kind": "MalformedAccount"})
    for mint, item in balances.items():
        identity = registry.get(mint, {})
        item.update(quantity=float(Decimal(item["raw_amount"]) / Decimal(10) ** item["decimals"]),
                    raw_amount=str(item["raw_amount"]),
                    ticker=identity.get("ticker", "UNKNOWN"),
                    classification=identity.get("classification", "unknown"),
                    identity_source=identity.get("source"),
                    pending_review=identity.get("approved") is not True,
                    managed_eligible=identity.get("approved") is True)
    return balances, errors


class SolanaOndoInventory:
    """Broad SPL inventory. Known mappings do not authorize creating a position."""
    def __init__(self, *, http=None, urls=None, registry=None):
        self.http = http
        self.urls = urls
        self.registry = {mint: {"ticker": info[1], "classification": "tokenized_equity",
                                "approved": True, "source": "Rocket reviewed ONDO mint registry"}
                         for mint, info in KNOWN_ONDO.items()}
        if registry:
            self.registry.update(registry)
        configured = env("ROCKET_ASSET_REGISTRY")
        if configured and registry is None:
            import json
            from pathlib import Path
            raw = json.loads(Path(configured).expanduser().read_text())
            if not isinstance(raw, dict) or any(not isinstance(row, dict) or not row.get("source") or not row.get("classification") for row in raw.values()):
                raise ValueError("invalid caller reviewed asset registry")
            self.registry.update(raw)

    @staticmethod
    def _rpc(client, url, method, params):
        response = client.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        response.raise_for_status()
        raw = response.json()
        if raw.get("error") or "result" not in raw:
            raise ValueError("RPC error or missing result")
        return raw["result"]

    def _snapshot(self, client, url, address):
        if self._rpc(client, url, "getGenesisHash", []) != MAINNET_GENESIS:
            raise ValueError("RPC network identity mismatch")
        balances, errors, slots = {}, [], []
        for program in TOKEN_PROGRAMS:
            raw = self._rpc(client, url, "getTokenAccountsByOwner",
                            [address, {"programId": program}, {"encoding": "jsonParsed", "commitment": "finalized"}])
            slot = raw["context"]["slot"]
            if not isinstance(slot, int) or slot <= 0:
                raise ValueError("invalid RPC slot")
            slots.append(slot)
            parsed, malformed = parse_accounts(raw["value"], program=program, address=address,
                                                registry=self.registry)
            if set(parsed) & set(balances):
                raise ValueError("mint belongs to conflicting token programs")
            balances.update(parsed)
            errors.extend(malformed)
        if max(slots) - min(slots) > 150:
            raise ValueError("RPC snapshot slots diverged")
        return balances, errors, min(slots)

    def _movement(self, client, url, address, mint, previous):
        """Bounded owner/account history. No sale is inferred from disappearance."""
        signatures = {}
        for account in [address, *previous.get("token_accounts", [])][:5]:
            rows = self._rpc(client, url, "getSignaturesForAddress", [account, {"limit": 20, "commitment": "finalized"}])
            if not isinstance(rows, list):
                raise ValueError("invalid signatures")
            for row in rows:
                if not row.get("err") and row.get("signature"):
                    signatures[row["signature"]] = row
        movements = []
        inspected = 0
        since = previous.get("observed_at")
        since_ms = None
        if since:
            try:
                since_ms = datetime.fromisoformat(str(since).replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError):
                pass
        ordered = sorted(signatures, key=lambda s: signatures[s].get("blockTime") or 0, reverse=True)
        for signature in ordered[:20]:
            if since_ms and signatures[signature].get("blockTime") and signatures[signature]["blockTime"] < since_ms:
                continue
            inspected += 1
            tx = self._rpc(client, url, "getTransaction", [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0, "commitment": "finalized"}])
            if not isinstance(tx, dict) or not isinstance(tx.get("meta"), dict) or tx["meta"].get("err"):
                continue
            meta = tx["meta"]
            if "preTokenBalances" not in meta or "postTokenBalances" not in meta:
                continue
            def total(key, meta=meta):
                return sum(Decimal(r["uiTokenAmount"]["amount"]) / Decimal(10) ** r["uiTokenAmount"]["decimals"]
                           for r in meta[key] if r.get("owner") == address and r.get("mint") == mint)
            delta = total("postTokenBalances") - total("preTokenBalances")
            if delta:
                instructions = tx.get("transaction", {}).get("message", {}).get("instructions", [])
                only_transfers = bool(instructions) and all(
                    i.get("parsed", {}).get("type") in {"transfer", "transferChecked", "closeAccount"}
                    and i.get("programId") in TOKEN_PROGRAMS for i in instructions)
                block_time = tx.get("blockTime")
                if since_ms and block_time and block_time < since_ms:
                    continue
                movements.append({"signature": signature, "mint": mint, "delta": str(delta), "block_time": block_time,
                                  "timestamp": datetime.fromtimestamp(block_time, UTC).isoformat() if block_time else None,
                                  "kind": "TRANSFER" if only_transfers else "OUTFLOW_UNCLASSIFIED" if delta < 0 else "INFLOW_UNCLASSIFIED"})
        return {"kind": movements[0]["kind"] if movements else "BALANCE_CHANGE_CAUSE_UNKNOWN",
                "history_inspected": True, "history_complete": False, "transactions": movements,
                "since": since, "transactions_inspected": inspected,
                "scope": "up to 20 transactions across up to 5 accounts; not proof of sale or complete history"}

    def fetch(self, *, address: str, now=None, previous=None) -> ProviderResult:
        from rocket.providers.dispatch import failure_kind
        previous = previous or {}
        owns = self.http is None
        client = self.http or httpx.Client(timeout=20)
        attempts, snapshots, parser_errors = [], [], []
        try:
            for url in self.urls or rpc_order():
                # Host labels exclude query credentials and private endpoint paths.
                host = urlsplit(url).hostname or "rpc"
                if any(s[0] == host for s in snapshots):
                    continue
                try:
                    balances, errors, slot = self._snapshot(client, url, address)
                    parser_errors.extend(errors)
                    if errors:
                        attempts.append({"name": host, "status": "PARTIAL", "failure_kind": "MalformedAccounts"})
                        continue
                    attempts.append({"name": host, "status": "HEALTHY", "slot": slot})
                    snapshots.append((host, balances, slot, url))
                    zeros = not any(float(r["quantity"]) > 0 for r in balances.values()) or any(
                        float(r.get("quantity", 0)) > 0 and float(balances.get(m, {}).get("quantity", 0)) == 0
                        for m, r in previous.items())
                    if not zeros and len(snapshots) == 1:
                        break
                    if len(snapshots) == 2:
                        break
                except Exception as exc:
                    attempts.append({"name": host, "status": "UNAVAILABLE", "failure_kind": failure_kind(exc)})
            if not snapshots:
                return ProviderResult(OperationalStatus.UNAVAILABLE, source="solana", failure_kind="NoValidSnapshot",
                                      extras={"provider_attempts": attempts, "parser_errors": parser_errors})
            host, balances, slot, url = snapshots[0]
            zeros = not any(float(r["quantity"]) > 0 for r in balances.values()) or any(
                float(r.get("quantity", 0)) > 0 and float(balances.get(m, {}).get("quantity", 0)) == 0 for m, r in previous.items())
            if zeros:
                if len(snapshots) < 2:
                    raise ValueError("EmptyConfirmationMissing")
                for _, _, confirmed_slot, endpoint in snapshots:
                    block_time = self._rpc(client, endpoint, "getBlockTime", [confirmed_slot])
                    if not isinstance(block_time, int) or isinstance(block_time, bool) or not 0 <= (now or datetime.now(UTC)).timestamp() - block_time <= 300:
                        raise ValueError("StaleRPCSnapshot")
                other = snapshots[1][1]
                keys = set(balances) | set(other)
                if abs(slot - snapshots[1][2]) > 150 or any(
                    balances.get(m, {}).get("raw_amount", "0") != other.get(m, {}).get("raw_amount", "0") for m in keys):
                    raise ValueError("RPCDisagreement")
            for mint, old in previous.items():
                if float(old.get("quantity", 0)) > 0 and float(balances.get(mint, {}).get("quantity", 0)) == 0:
                    balances[mint] = {**old, **balances.get(mint, {}), "quantity": 0, "raw_amount": "0",
                                      "zero_confirmed": True}
                row = balances.get(mint)
                if row is not None and Decimal(str(old.get("quantity", 0))) != Decimal(str(row["quantity"])):
                    try:
                        movement = self._movement(client, url, address, mint, old)
                    except Exception as exc:
                        # A history outage does not invalidate independently verified balances.
                        movement = {"kind": "BALANCE_CHANGE_CAUSE_UNKNOWN", "history_inspected": False,
                                    "history_complete": False, "transactions": [],
                                    "failure_kind": failure_kind(exc)}
                    row["movement"] = {**movement, "previous_quantity": old.get("quantity"),
                                       "current_quantity": row["quantity"]}
            # Unknown metadata is descriptive only and cannot authorize promotion.
            for mint, row in balances.items():
                if row["ticker"] == "UNKNOWN":
                    try:
                        account = self._rpc(client, url, "getAccountInfo", [mint, {"encoding": "jsonParsed", "commitment": "finalized"}])
                        value = account.get("value") or {}
                        if value.get("owner") == row["token_program"]:
                            row["mint_metadata"] = {"token_program": value["owner"], "mint_account_observed": True}
                            info = value.get("data", {}).get("parsed", {}).get("info", {})
                            for extension in info.get("extensions", []):
                                metadata = extension.get("state", {})
                                if extension.get("extension") == "tokenMetadata" and metadata.get("mint") == mint:
                                    row["mint_metadata"].update(display_name=metadata.get("name"), symbol=metadata.get("symbol"),
                                                                metadata_trust="issuer asserted; does not establish investment classification")
                    except Exception:
                        row["identification_failure"] = "MintMetadataUnavailable"
                row["snapshot_slot"] = slot
                row["observed_at"] = (now or datetime.now(UTC)).isoformat()
                row["confirmed_by"] = [s[0] for s in snapshots]
            return ProviderResult(OperationalStatus.HEALTHY, tuple(balances.values()), now or datetime.now(UTC), source="solana",
                                  extras={"provider_attempts": attempts, "parser_errors": parser_errors,
                                          "empty_confirmed": zeros, "supported_token_programs": list(TOKEN_PROGRAMS)})
        except Exception as exc:
            kind = str(exc) if isinstance(exc, ValueError) and str(exc) in {"RPCDisagreement", "EmptyConfirmationMissing", "StaleRPCSnapshot"} else failure_kind(exc)
            return ProviderResult(OperationalStatus.UNAVAILABLE, source="solana", failure_kind=kind,
                                  extras={"provider_attempts": attempts, "parser_errors": parser_errors})
        finally:
            if owns:
                client.close()
