"""Score frozen FUT-013 BTC spot lead-lag transfer to ETH/SOL perps."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
from pathlib import Path
import random
import statistics
import zipfile

from research.futures.cross_crypto_minute_source_audit import audit_zip


MONTHS = ("2024-11", "2025-04", "2025-08")
TARGETS = ("ETHUSDT", "SOLUSDT")
MINUTE_MS = 60_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bars(raw: bytes, month: str) -> list[tuple[float, float, float, float]]:
    """Return ordered open, close, base and quote volume after source audit."""
    counts, stamps = audit_zip(raw, month)
    if counts["missing_minutes"] or counts["rows"] != counts["expected_minutes"]:
        raise ValueError(f"incomplete source month {month}")
    first = min(stamps)
    data = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        with archive.open(archive.namelist()[0]) as member:
            reader = csv.reader(io.TextIOWrapper(member, encoding="utf-8-sig"))
            for row in reader:
                if row and row[0].lower().replace(" ", "_") == "open_time":
                    continue
                unit = 1000 if len(row[0]) == 16 else 1
                stamp = int(row[0]) // unit
                if stamp != first + len(data) * MINUTE_MS:
                    raise ValueError(f"unsorted or missing minute {month}/{stamp}")
                data.append((float(row[1]), float(row[4]), float(row[5]), float(row[7])))
    return data


def summary(events: list[dict]) -> dict:
    if not events:
        return {"n": 0, "gross_mean_bp": None, "gross_median_bp": None,
                "always_long_mean_bp": None, "always_short_mean_bp": None,
                "own_lag_mean_bp": None, "base_fee_floor_mean_bp": None,
                "ten_bp_per_side_mean_bp": None}
    gross = [e["gross_bp"] for e in events]
    longs = [e["long_bp"] for e in events]
    own = [e["own_lag_bp"] for e in events]
    mean_gross = statistics.mean(gross)
    long_mean = statistics.mean(longs)
    return {"n": len(events), "gross_mean_bp": mean_gross,
            "gross_median_bp": statistics.median(gross),
            "always_long_mean_bp": long_mean,
            "always_short_mean_bp": -long_mean,
            "own_lag_mean_bp": statistics.mean(own),
            "base_fee_floor_mean_bp": mean_gross - 9,
            "ten_bp_per_side_mean_bp": mean_gross - 20}


def day_block_interval(events: list[dict], seed: int) -> list[float]:
    if not events:
        return []
    groups: dict[tuple[str, int], list[float]] = collections.defaultdict(list)
    for event in events:
        groups[(event["month"], event["day_index"])].append(event["gross_bp"])
    totals = [(sum(group), len(group)) for group in groups.values()]
    rng = random.Random(seed)
    means = []
    for _ in range(10_000):
        chosen = [rng.choice(totals) for _ in totals]
        means.append(sum(item[0] for item in chosen) / sum(item[1] for item in chosen))
    means.sort()
    return [means[250], means[9750]]


def score(manifest_path: Path, root: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    if tuple(manifest["months"]) != MONTHS or len(manifest["files"]) != 9:
        raise ValueError("source manifest differs from frozen contract")
    by_month: dict[str, dict[str, list[tuple[float, float, float, float]]]] = (
        collections.defaultdict(dict)
    )
    source_counts = {}
    for item in manifest["files"]:
        key = item["source_key"]
        month = next((month for month in MONTHS if key.endswith(f"-{month}.zip")), None)
        symbol = next((symbol for symbol in ("BTCUSDT", *TARGETS) if f"/{symbol}/1m/" in key), None)
        if month is None or symbol is None or symbol in by_month[month]:
            raise ValueError(f"unexpected or duplicate source {key}")
        if (symbol == "BTCUSDT") != ("/spot/" in key):
            raise ValueError(f"wrong market for {symbol}")
        path = root / key
        if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise ValueError(f"source size or SHA mismatch: {key}")
        raw = path.read_bytes()
        by_month[month][symbol] = bars(raw, month)
        source_counts[key] = len(by_month[month][symbol])
    if any(set(by_month[month]) != {"BTCUSDT", *TARGETS} for month in MONTHS):
        raise ValueError("missing source market")

    events: list[dict] = []
    dispositions: dict[str, dict[str, dict[str, int]]] = {}
    direction_counts: dict[str, dict[str, dict[str, int]]] = {}
    for month in MONTHS:
        btc = by_month[month]["BTCUSDT"]
        if any(len(by_month[month][target]) != len(btc) for target in TARGETS):
            raise ValueError(f"source clock mismatch: {month}")
        dispositions[month] = {}
        direction_counts[month] = {}
        for target in TARGETS:
            target_bars = by_month[month][target]
            cash = collections.Counter()
            signs = collections.Counter()
            for t in range(10, len(btc) - 11, 10):
                cash["scheduled"] += 1
                prior_btc = btc[t - 1]
                prior_target = target_bars[t - 1]
                entry = target_bars[t + 1]
                exit_bar = target_bars[t + 11]
                if any(bar[2] <= 0 or bar[3] <= 0 for bar in
                       (prior_btc, prior_target, entry, exit_bar)):
                    cash["cash_zero_volume_source_or_proxy"] += 1
                    continue
                signal = (prior_btc[1] > prior_btc[0]) - (prior_btc[1] < prior_btc[0])
                if signal == 0:
                    cash["cash_flat_btc_minute"] += 1
                    continue
                own = (prior_target[1] > prior_target[0]) - (
                    prior_target[1] < prior_target[0]
                )
                long_bp = 10_000 * (exit_bar[0] / entry[0] - 1)
                events.append({"month": month, "target": target, "day_index": t // 1440,
                               "signal": signal, "gross_bp": signal * long_bp,
                               "long_bp": long_bp, "own_lag_bp": own * long_bp})
                signs["long" if signal > 0 else "short"] += 1
                cash["active"] += 1
            dispositions[month][target] = dict(cash)
            direction_counts[month][target] = dict(signs)

    by_cell = {f"{month}/{target}": summary([
        e for e in events if e["month"] == month and e["target"] == target
    ]) for month in MONTHS for target in TARGETS}
    checks = [by_cell[f"{month}/{target}"] for month in MONTHS[1:] for target in TARGETS]
    sample_pass = all(cell["n"] >= 1000 for cell in checks)
    gross_pass = sample_pass and all(
        cell["gross_mean_bp"] > 9
        and cell["gross_mean_bp"] > cell["always_long_mean_bp"]
        and cell["gross_mean_bp"] > cell["always_short_mean_bp"]
        and cell["gross_mean_bp"] > cell["own_lag_mean_bp"]
        for cell in checks
    )
    status = ("NO_SAMPLE" if not sample_pass else
              "CHEAP_GROSS_GATE_PASSED_NEEDS_EXECUTION_AND_VENUE_VALIDATION" if gross_pass else
              "GROSS_OR_INCREMENTAL_FEE_FLOOR_FAILED")
    return {"status": status, "source_counts": source_counts,
            "dispositions": dispositions, "direction_counts": direction_counts,
            "by_target_month": by_cell, "pooled": summary(events),
            "pooled_day_block_95pct_bp": day_block_interval(events, 20260925),
            "by_target_day_block_95pct_bp": {
                target: day_block_interval([e for e in events if e["target"] == target],
                                           20260925 + index)
                for index, target in enumerate(TARGETS)
            },
            "sample_gate_pass": sample_pass,
            "gross_and_control_gate_pass": gross_pass if sample_pass else None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("source_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(score(args.manifest, args.source_root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
