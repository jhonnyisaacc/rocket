"""Run synthetic feasibility on the single approved structural input, never outcomes."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

from rocket.research.power import GATES, run

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "research/governance/power"
GEOMETRY = FOLDER / "population.geometry.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draws", type=int, default=2000)
    parser.add_argument("--bootstrap-draws", type=int, default=2000)
    args = parser.parse_args()
    if args.draws < 1 or args.bootstrap_draws < 20:
        raise ValueError("Positive Monte Carlo count and >=20 bootstrap draws required")
    if GEOMETRY.is_symlink():
        raise ValueError("Structural input must be a regular file")
    raw = GEOMETRY.read_bytes()
    report = run(json.loads(raw), args.draws, args.bootstrap_draws,
                 progress=lambda *regime: print(regime, flush=True))
    report["geometry_sha256"] = hashlib.sha256(raw).hexdigest()
    report["code_sha256"] = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                             for p in ("rocket/research/power.py", "scripts/research/power_audit.py")}
    (FOLDER / "surface.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    with (FOLDER / "surface.csv").open("w") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scenario", "missingness", "r", "economic_drift_S", "mean_alerts", "mean_total_cap", *GATES, "binding_gate"])
        for row in report["results"]:
            writer.writerow([row["scenario"], row["missingness"], row["synthetic_r"], row["economic_drift_S"], row["mean_alerts"], row["mean_total_cap"],
                             *(row["probabilities"][gate]["probability"] for gate in GATES), row["binding_gate_by_marginal_probability"]])
    print(json.dumps({"conclusion": report["conclusion"], "geometry": report["geometry"]}), flush=True)


if __name__ == "__main__":
    main()
