"""Additional post-replay checks; do not alter the sealed strategy or fixtures."""
import copy,json,unittest
from pathlib import Path
from engine import *
from execution import simulate
from research import finer_btc,compute_frames,sha,ROOT

def bar(i,o,h,l,c):return dict(t=i*H,o=o,h=h,l=l,c=c)

class AuditTests(unittest.TestCase):
    def fixture(self):
        bars=[bar(0,97,100,95,98),bar(1,98,101,94,99),bar(2,99,102,93,100),
          bar(3,98,101,92,95),bar(4,95,100,90,94),bar(5,94,101,92,97),bar(6,97,100,93,96),
          bar(7,94,101,89,95),bar(8,95,103,94,103),bar(9,103,104,101,103),
          bar(10,103,136,102,130),bar(11,130,131,80,85)]
        h=dict(time=7*H,direction=1,leg=dict(origin=80),candidate=dict(zone=[90,104]),targets=[125,135],passive_stop=89)
        rates=[dict(time=i*H,fundingRate=.00001) for i in range(13)]
        return bars,h,rates
    def test_full_flip_lifecycle_fixture(self):
        bs,h,rates=self.fixture();r=simulate(bs,h,'flip','OLHC',rates)
        self.assertEqual(r['trigger_time'],10*H)
        self.assertEqual(r['entry_time'],10*H)
        self.assertEqual(r['entry'],103)
        self.assertEqual(r['status'],'closed')
        self.assertAlmostEqual(sum(e['quantity'] for e in r['exits']),1)
        self.assertEqual([e['reason'] for e in r['exits']],['target1','target2','stop'])
        self.assertIsNotNone(r['economics']['net']['40'])
    def test_trigger_prefix_cannot_see_next_entry(self):
        bs,h,rates=self.fixture();r=simulate(bs[:10],h,'flip','OLHC',rates)
        self.assertEqual(r['trigger_time'],10*H);self.assertNotIn('entry',r)
        self.assertEqual(r['status'],'unresolved_pending')
    def test_stop_and_origin_are_separate(self):
        bs,h,rates=self.fixture();before=copy.deepcopy(h)
        r=simulate(bs,h,'flip','OLHC',rates)
        self.assertEqual(h,before);self.assertNotEqual(r['initial_stop'],r['origin'])
    def test_position_censoring_not_realized_win(self):
        bs,h,rates=self.fixture();r=simulate(bs[:11],h,'flip','OLHC',rates)
        self.assertEqual(r['status'],'unresolved_position')
        self.assertAlmostEqual(r['remaining'],.1);self.assertIsNone(r['economics']['net']['20'])
    def test_frozen_stop_does_not_follow_fresh_frame(self):
        bs,h,rates=self.fixture();r=simulate(bs,h,'flip','OLHC',rates)
        self.assertAlmostEqual(r['initial_stop'],89*.9999)
    def test_exact_replay_fixture(self):
        bs,h,rates=self.fixture()
        self.assertEqual(simulate(bs,h,'flip','OHLC',rates),simulate(bs,h,'flip','OHLC',rates))
    def test_passive_is_different_policy(self):
        bs,h,rates=self.fixture();r=simulate(bs,h,'passive','OLHC',rates)
        self.assertEqual(r['entry_time'],7*H);self.assertNotIn('trigger_time',r)
    def test_invalidation_before_pending_entry(self):
        bs,h,rates=self.fixture();r=simulate(bs,h,'flip','OLHC',rates,[8*H])
        self.assertEqual(r['status'],'invalidated_before_entry');self.assertNotIn('entry',r)
    def test_finer_data_aggregate(self):
        bs=json.loads((ROOT/'inputs/hourly.json').read_text())['assets']['BTC'];fine=finer_btc(bs)
        self.assertGreater(len(fine),0)
        for t,rs in fine.items():self.assertEqual(len(rs),12)
    def test_seal_unchanged(self):
        for p,digest in json.loads((ROOT/'contract_seal.json').read_text())['hashes'].items():self.assertEqual(sha(ROOT/p),digest)
    def test_targets_do_not_skip_closer_swing(self):
        # Strict confirmed nearest opposing swing is preserved before any RR check.
        bs=[bar(i,100,h,90,99) for i,h in enumerate([100,101,105,101,100,101,120,101,100])]
        self.assertEqual(objectives(bs,[],[90,100],1),[]) # hourly timestamps are NOT valid 4h pivots
        bs=[dict(b,t=b['t']*4) for b in bs]
        self.assertEqual(objectives(bs,[],[90,100],1),[105,120])

if __name__=='__main__':unittest.main()
