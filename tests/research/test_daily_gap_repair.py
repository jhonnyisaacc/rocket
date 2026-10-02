"""Daily repair requests every missing day only for bounded active gaps."""

import sqlite3
from datetime import date

from research.futures.daily_gap_repair import day_ms, gap_tasks
from research.futures.normalize_archives import initialize


def test_gap_tasks_require_both_active_neighbors():
    db = sqlite3.connect(":memory:")
    initialize(db)
    for symbol, day in [("AUSDT", date(2022, 2, 25)),
                        ("AUSDT", date(2022, 3, 1)),
                        ("BUSDT", date(2022, 2, 25))]:
        db.execute("INSERT INTO prices VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (symbol, day_ms(day), 1, 2, 0.5, 1, 100, 100, 1, "source"))
    assert gap_tasks(db, date(2022, 2, 26), date(2022, 2, 28)) == [
        ("AUSDT", date(2022, 2, 26)),
        ("AUSDT", date(2022, 2, 27)),
        ("AUSDT", date(2022, 2, 28)),
    ]
