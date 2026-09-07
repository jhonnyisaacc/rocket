from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "rocket"
MARKERS = ("~/.hermes", "~/.openclaw", "~/.nanobot", "HERMES_HOME")


def test_package_has_no_bot_runtime_path_defaults():
    hits: list[str] = []
    for path in ROOT.rglob("*.py"):
        if path.name == "config.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "FORBIDDEN" in line or "forbidden" in line.lower():
                continue
            for marker in MARKERS:
                if marker in line:
                    hits.append(f"{path.relative_to(ROOT.parent)}:{number}: {marker}")
    assert hits == []
