"""Optional loader for the Cava prediction scorecard. Not required for the check."""

from __future__ import annotations

import csv
import re
from datetime import date, timedelta
from pathlib import Path

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def load_scorecard(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def pending_due(rows: list[dict[str, str]], asof: date, *, within_days: int) -> list[dict[str, str]]:
    """Pending calls whose notes contain a check date inside the window."""
    horizon = asof + timedelta(days=within_days)
    due = []
    for row in rows:
        status = (row.get("status") or "").lower()
        if "pending" not in status:
            continue
        text = " ".join(row.get(key) or "" for key in ("deadline_check_date", "notes", "testable_metric"))
        stamps = [date.fromisoformat(match) for match in _DATE.findall(text)]
        soon = [stamp for stamp in stamps if asof <= stamp <= horizon]
        if not soon:
            continue
        due.append({
            "id": row.get("id") or "",
            "claim": row.get("claim") or "",
            "status": row.get("status") or "",
            "next_date": min(soon).isoformat(),
        })
    due.sort(key=lambda item: (item["next_date"], item["id"]))
    return due
