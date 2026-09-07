from rocket.models import OperationalReport, OperationalStatus, ResearchResult, ResearchStatus
from rocket.store import ResearchStore


def test_runs_are_append_only(tmp_path, now):
    store = ResearchStore(tmp_path)
    result = ResearchResult(
        workflow="fixture.scan",
        status=ResearchStatus.NO_SETUP,
        operational=OperationalReport(status=OperationalStatus.HEALTHY),
        decision_time=now,
        started_at=now,
        completed_at=now,
        run_id="run-1",
    )
    path = store.save_result(result)
    assert path.exists()
    loaded = store.load_result("fixture.scan")
    assert loaded is not None and loaded.run_id == "run-1"
    try:
        store.save_result(result)
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("run journal must not overwrite a run_id")
