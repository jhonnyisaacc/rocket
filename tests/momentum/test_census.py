from rocket.momentum.census import concentration, distribution, segment_legs
from rocket.momentum.core import FOUR_HOURS, candidates
from tests.momentum.test_core import bar, history


def test_statistics_do_not_treat_rows_as_independent_episodes():
    assert concentration([10.0, 0.0, 0.0])["kish_n"] == 1.0
    assert concentration([1.0, 1.0, 1.0])["kish_n"] == 3.0
    assert distribution([])["median"] is None
    assert distribution([1.0, 2.0, 3.0])["median"] == 2.0


def test_diagnostic_leg_is_ex_post_and_never_changes_candidates():
    bars = history(181)
    for i in range(181, 195):
        bars.append(bar(i * FOUR_HOURS, 100 + (i - 180) * 2.0, interval=FOUR_HOURS))
    before, _ = candidates(bars)
    for i in range(195, 210):
        bars.append(bar(i * FOUR_HOURS, 128 - (i - 194) * 2.0, interval=FOUR_HOURS))
    after, _ = candidates(bars)
    assert before == [e for e in after if e.data_cutoff <= 195 * FOUR_HOURS]
    legs = segment_legs(bars, after)
    assert legs
    assert all(l["reversal_observed_at"] > l["end"] for l in legs)
    assert all(0 <= l["consumed_oracle"]["4"] <= 1 for l in legs)
    assert segment_legs(bars, after) == legs


def test_every_new_extremum_updates_its_reversal_scale(monkeypatch):
    import math
    from types import SimpleNamespace

    from rocket.momentum import census

    rows = [bar(i * FOUR_HOURS, interval=FOUR_HOURS) for i in range(180)]
    prices = (100.0, 106.0, 108.0, 102.5)
    rows += [bar((180 + i) * FOUR_HOURS, p, interval=FOUR_HOURS) for i, p in enumerate(prices)]
    scales = dict(zip((b.end_time for b in rows[-4:]), (0.03, 0.04, 0.05, 0.01)))
    monkeypatch.setattr(
        census,
        "snapshot",
        lambda bars, decision, cutoff: SimpleNamespace(sigma=scales.get(cutoff, 0) / math.sqrt(42)),
    )
    audit = {}
    legs = census.segment_legs(rows, [], audit=audit)
    assert len(legs) == 1
    assert legs[0]["start"] == rows[180].end_time
    # 108 is a new high even though its advance from 106 is less than 1S.
    assert legs[0]["end"] == rows[182].end_time
    assert legs[0]["reversal_observed_at"] == rows[183].end_time
    assert legs[0]["normalized_magnitude"] == math.log(108 / 100) / 0.03
    assert audit["completed_legs"] == 1
    assert audit["censored_tail"]["direction"] == -1
