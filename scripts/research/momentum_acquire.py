"""Acquire checksum-verified Binance archives for the momentum program.

Usage: python3 scripts/research/momentum_acquire.py <data-dir>
Writes MANIFEST.json. Re-runnable; skips verified files.
"""

from __future__ import annotations

import json
import sys

from rocket.momentum.acquire import acquire_all


def main() -> int:
    directory = sys.argv[1] if len(sys.argv) > 1 else "artifacts/momentum/data"
    manifest = acquire_all(directory)
    print(json.dumps(
        {"files": len(manifest["files"]), "missing": len(manifest["missing"]),
         "metrics_days": manifest.get("n_metrics_days")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
