"""Audit a public RED-COHORT archive without executing its bundled code.

Usage: python3 audit_cohort_archive.py ARCHIVE.zip
Prints JSON; this is a source-data audit, not a return backtest.
"""
import collections
import gzip
import hashlib
import json
import statistics
import sys
import zipfile
from pathlib import Path


def valid_address(address):
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    if not 32 <= len(address) <= 44 or any(c not in alphabet for c in address):
        return False
    n = 0
    for c in address:
        n = n * 58 + alphabet.index(c)
    return len(address) - len(address.lstrip("1")) + (n.bit_length() + 7) // 8 == 32


def audit(path):
    with open(path, "rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    with zipfile.ZipFile(path) as archive:
        prefix = "RED-COHORT-2026-v1/"
        cohorts = [json.loads(line) for line in archive.read(prefix + "sniper_cohorts.jsonl").splitlines()]
        intra = [json.loads(line) for line in gzip.decompress(archive.read(prefix + "sniper_cohorts_intra.jsonl.gz")).splitlines()]
        published = json.loads(archive.read(prefix + "psm_results_nocohort_zerofill.json"))
        required = ["pumpfun_buyers.jsonl", "pumpfun_launches.jsonl"]
        missing = [name for name in required if not any(p.endswith('/' + name) for p in archive.namelist())]
    wallets = {w for c in cohorts for w in c["wallets"]}
    hits = [h for c in cohorts for h in c["mints_hit"]]
    top = cohorts[0]
    summary = {
        "edge": "NO_EDGE_VALIDATED",
        "source": "https://zenodo.org/records/21765387",
        "archive_sha256": digest,
        "cohorts": len(cohorts),
        "unique_wallet_strings": len(wallets),
        "valid_solana_addresses": sum(map(valid_address, wallets)),
        "invalid_or_redacted_strings": sum(not valid_address(w) for w in wallets),
        "cohort_size_distribution": dict(sorted(collections.Counter(c["cohort_size"] for c in cohorts).items())),
        "size_field_mismatches": sum(c["cohort_size"] != len(set(c["wallets"])) for c in cohorts),
        "distinct_catalogue_mints": len({h["mint"] for h in hits}),
        "catalogue_hit_rows": len(hits),
        "intra_rows": len(intra),
        "intra_distinct_mints": len({r["mint"] for r in intra}),
        "intra_first_rank_above_10": sum(r["first_rank"] > 10 for r in intra),
        "intra_duplicate_wallet_rows": sum(len(r["wallets"]) != len(set(r["wallets"])) for r in intra),
        "intra_duplicate_signature_rows": sum(len(r.get("tx_sigs", [])) != len(set(r.get("tx_sigs", []))) for r in intra),
        "intra_missing_available_at": sum("available_at" not in r for r in intra),
        "missing_full_corpus_files": missing,
        "published_results_are_not_reproduced": True,
        "published_results": published,
        "top_cohort": {
            "wallets": top["wallets"],
            "launches": top["n_launches"],
            "first_seen": top["first_seen_iso"],
            "last_seen": top["last_seen_iso"],
            "median_cohort_sol_per_hit": statistics.median(h["sum_sol"] for h in top["mints_hit"]),
            "hits_below_0_2_sol": sum(h["sum_sol"] < .2 for h in top["mints_hit"]),
            "same_second_hits": sum(h["min_time"] == h["max_time"] for h in top["mints_hit"]),
            "mean_first_rank": top["avg_first_rank"],
            "warning": "Historical discovery sample; no price, sell, profitability or current activity validation.",
        },
    }
    return summary


if __name__ == "__main__":
    result = audit(sys.argv[1])
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if len(sys.argv) > 2:
        output = Path(sys.argv[2])
        output.mkdir(parents=True, exist_ok=True)
        (output / "archive_audit.json").write_text(rendered + "\n")
        with zipfile.ZipFile(sys.argv[1]) as archive:
            cohorts = [json.loads(line) for line in archive.read("RED-COHORT-2026-v1/sniper_cohorts.jsonl").splitlines()]
        candidates = {}
        for index, cohort in enumerate(cohorts):
            for address in cohort["wallets"]:
                if not valid_address(address):
                    continue
                row = candidates.setdefault(address, {
                    "address": address, "chain_id": "solana:mainnet",
                    "source": result["source"], "source_archive_sha256": result["archive_sha256"],
                    "attribution": "Arati Uday Kamat, RED-COHORT-2026-v1, CC-BY-4.0",
                    "status": "HISTORICAL_CANDIDATE_UNVALIDATED", "username": None,
                    "profitability": None, "live_eligible": False, "catalogue_rows": [],
                })
                row["catalogue_rows"].append(index + 1)
        (output / "wallet_candidates.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for _, row in sorted(candidates.items())))
        print(json.dumps({"audit": str(output / "archive_audit.json"), "wallets": len(candidates)}))
    else:
        print(rendered)
