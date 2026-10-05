"""Published review/archive evidence stays bounded and hash-identical."""

import hashlib
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

import pytest

from rocket.research.power import validate_geometry

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("issue", [51, 58])
def test_review_packet_integrity_and_unresolved_acceptance(issue):
    manifest = json.loads((ROOT / f"research/governance/review_packets/foundation-{issue}.json").read_bytes())
    bundle = ROOT / manifest["bundle_path"]
    assert hashlib.sha256(bundle.read_bytes()).hexdigest() == manifest["bundle_sha256"]
    assert manifest["state"] == "PENDING_EXTERNAL_REVIEW"
    assert manifest["predictive_trials_consumed"] == 0
    assert manifest["scoring_authorized"] is False
    with ZipFile(bundle) as archive:
        expected = {f["path"] for f in manifest["files"]}
        assert set(archive.namelist()) == expected | {
            "source_manifest.json", "README.md", "verify_packet.py", "review_decision_template.json"}
        for entry in archive.infolist():
            path = PurePosixPath(entry.filename)
            assert not path.is_absolute() and ".." not in path.parts
            assert entry.external_attr >> 16 == 0o100644
        assert json.loads(archive.read("source_manifest.json"))["files"] == manifest["files"]
        for record in manifest["files"]:
            assert hashlib.sha256(archive.read(record["path"])).hexdigest() == record["sha256"]
        decision = json.loads(archive.read("review_decision_template.json"))
        assert decision["decision"] == "PENDING_EXTERNAL_REVIEW"
        assert all(decision[k] is None for k in ("reviewer", "model_family", "contribution_history", "timestamp"))
        assert decision["scoring_authorized"] is False


def test_synthetic_review_packet_has_only_structural_real_data():
    path = ROOT / "research/governance/review_packets/foundation-58.zip"
    with ZipFile(path) as archive:
        names = archive.namelist()
        assert not any("/results/" in n or "/reconciliation/" in n or n.endswith((".db", ".sqlite", ".parquet")) for n in names)
        json_paths = {n for n in names if n.endswith(".json")}
        assert json_paths == {
            "source_manifest.json", "review_decision_template.json",
            "research/governance/power/population.geometry.json",
            "research/governance/power/environment.json", "research/governance/power/surface.json"}
        geometry = archive.read("research/governance/power/population.geometry.json")
        assert geometry == (ROOT / "research/governance/power/population.geometry.json").read_bytes()
        validate_geometry(json.loads(geometry))


@pytest.mark.parametrize("number", [26, 38, 40, 46])
def test_historical_archive_has_all_declared_exact_documents_and_no_runtime(number):
    folder = ROOT / f"docs/research/archive/pr-{number}"
    manifest = json.loads((folder / "manifest.json").read_bytes())
    assert manifest["pr"] == number
    assert manifest["trial_accounting_changed"] is False
    assert manifest["runtime_merged"] is False
    assert manifest["scientific_admission_granted"] is False
    assert manifest["predictive_trials_consumed_this_operation"] == 0
    assert {p.relative_to(ROOT).as_posix() for p in (folder / "docs").rglob("*") if p.is_file()} == {
        f["canonical_path"] for f in manifest["files"]}
    for record in manifest["files"]:
        path = ROOT / record["canonical_path"]
        assert path.suffix == ".md" and path.is_relative_to(folder)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
        assert record["source_url"].endswith(manifest["source_revision"] + "/" + record["source_path"])
    if number == 38:
        paths = {r["source_path"] for r in manifest["files"]}
        assert "docs/research/futures/experiments/FUT-001-OOS.md" in paths
        assert all(f"docs/research/futures/experiments/FUT-{i:03d}-RESULT.md" in paths for i in range(2, 14))
