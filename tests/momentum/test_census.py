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
