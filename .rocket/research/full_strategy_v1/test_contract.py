import unittest
from engine import *
from execution import execute_bar,economics,simulate

def bar(t,o=100,h=102,l=98,c=101):return dict(t=t,o=o,h=h,l=l,c=c)

class ContractTests(unittest.TestCase):
    def test_complete_periods_only(self):
        bs=[bar(i*H) for i in range(25)]
        self.assertEqual(len(aggregate(bs,D,23*H)),0)
        self.assertEqual(len(aggregate(bs,D,24*H)),1)
        self.assertEqual(aggregate(bs[:12]+bs[13:],D,25*H),[])
    def test_weekly_warmup_and_gap(self):
        ws=[bar(MONDAY+i*W,c=100+i) for i in range(9)]
        self.assertIsNone(velocity(ws[:8]));self.assertIsNotNone(velocity(ws))
        ws[-1]['t']+=W;self.assertIsNone(velocity(ws))
    def test_pivot_confirmation(self):
        bs=[bar(i*H,h=v) for i,v in enumerate([101,102,110,103,102])]
        self.assertEqual(pivots(bs[:4],2,H),[])
        self.assertEqual(pivots(bs,2,H)[0]['available'],5*H)
    def test_flat_not_trigger(self):
        h=dict(direction=1,candidate=dict(zone=[98,102]))
        self.assertEqual(flip_step({},[bar(i*H,o=100,h=100,l=100,c=100) for i in range(30)],h),{})
    def test_retest_after_break(self):
        h=dict(direction=1,candidate=dict(zone=[98,104]))
        bs=[bar(i*H,l=v) for i,v in enumerate([99,98,95,98,99])]+[bar(5*H,o=101,h=104,l=100,c=103)]
        got=flip_step(dict(swept=H,broken=4*H,level=101),bs,h)
        self.assertEqual(got['trigger'],6*H)
        self.assertLess(got['stop'],95)
    def test_release_availability(self):
        r=dict(available_at=10,expires_at=20)
        self.assertIsNone(available_context([r],9));self.assertEqual(available_context([r],10),r)
        self.assertIsNone(available_context([r],20));self.assertIsNone(available_context([{}],100))
    def test_schedule_boundary(self):
        self.assertEqual(next_run(11*H),11*H);self.assertEqual(next_run(11*H+1),17*H)
    def test_reaction_is_not_touch(self):
        self.assertFalse(reaction(bar(0,o=100,h=103,l=98,c=100),[98,102],1))
        self.assertTrue(reaction(bar(0,o=100,h=103,l=97,c=102),[98,102],1))
    def test_ben_adverse_side(self):
        self.assertLess(institutional(76339,70000,1),76339)
        self.assertGreater(institutional(1.1345,1, -1),1.1345)
    def position(self):
        return dict(direction=1,entry=100,risk=10,stop=90,remaining=1.,targets=[110,120],tp=0,exits=[])
    def test_partial_exit(self):
        p=self.position();execute_bar(p,bar(0,100,121,99,115),'OLHC')
        self.assertAlmostEqual(p['remaining'],.1)
        self.assertEqual([r['quantity'] for r in p['exits']],[.8,.1])
    def test_ambiguity_paths(self):
        a=self.position();b=self.position();c=bar(0,100,121,89,100)
        execute_bar(a,c,'OLHC');execute_bar(b,c,'OHLC')
        self.assertEqual(a['exits'][0]['reason'],'stop')
        self.assertEqual(b['exits'][0]['reason'],'target1')
    def test_gap_stop(self):
        p=self.position();execute_bar(p,bar(0,85,89,80,88),'OLHC')
        self.assertEqual(p['exits'][0]['price'],85)
    def test_target_before_limit_not_credited(self):
        p=dict(direction=1,stop=90,targets=[110,120],remaining=0.)
        execute_bar(p,bar(0,105,115,99,101),'OHLC',100)
        self.assertEqual(p['exits'],[])
    def test_missing_funding_not_zero(self):
        p=self.position();p.update(entry_time=0,entry_time_bounds=[0,0],end_time=H)
        execute_bar(p,bar(0,100,101,89,95),'OLHC')
        self.assertIsNone(economics(p,[])['net']['20'])
    def test_pending_expiry_boundary(self):
        h=dict(time=0,direction=1,leg=dict(origin=80),candidate=dict(zone=[90,100]),
               targets=[120,130],passive_stop=89)
        r=simulate([bar(8*D,o=100,h=101,l=99,c=100)],h,'passive','OLHC',[])
        self.assertEqual(r['status'],'expired');self.assertNotIn('entry',r)
    def test_no_next_bar_unresolved(self):
        h=dict(time=0,direction=1,leg=dict(origin=80),candidate=dict(zone=[90,100]),
               targets=[120,130],passive_stop=89)
        self.assertEqual(simulate([],h,'flip','OLHC',[])['status'],'unresolved_pending')
    def test_closer_objective_rejects(self):
        h=dict(time=0,direction=1,leg=dict(origin=80),candidate=dict(zone=[90,100]),
               targets=[105,130],passive_stop=89)
        r=simulate([bar(0,100,101,99,100)],h,'passive','OLHC',[])
        self.assertEqual(r['status'],'entry_risk_or_zone_rejected')
    def test_future_frame_invariance(self):
        bs=[bar(i*H) for i in range(200)]
        a=frame(bs,100*H)
        for b in bs[100:]: b.update(h=10000,l=1,c=9999)
        self.assertEqual(a,frame(bs,100*H))
    def test_short_partial_exit(self):
        p=dict(direction=-1,entry=100,risk=10,stop=110,remaining=1.,targets=[90,80],tp=0,exits=[])
        execute_bar(p,bar(0,100,101,79,85),'OHLC')
        self.assertAlmostEqual(p['remaining'],.1)
    def test_finer_bar_timestamps(self):
        p=self.position();b=bar(H//12,100,101,89,95);b['_step']=H//12
        execute_bar(p,b,'OLHC')
        self.assertEqual(p['exits'][0]['time_bounds'],[H//12,H//6])
    def test_funding_partial_quantity(self):
        p=self.position();p.update(entry_time=0,entry_time_bounds=[0,0],end_time=3*H)
        p['remaining']=0.;p['exits']=[dict(quantity=.8,price=110,time=H,time_bounds=[H,H]),dict(quantity=.2,price=90,time=3*H,time_bounds=[3*H,3*H])]
        rates=[dict(time=i*H,fundingRate=.001) for i in range(4)]
        result=economics(p,rates)
        self.assertEqual(result['funding_missing_hours'],[])
        self.assertLess(result['funding_cost_bounds_r'][1],.04)
    def test_daily_structure_not_sma(self):
        ps=[dict(side=1,price=100),dict(side=-1,price=90),dict(side=1,price=101),dict(side=-1,price=91)]
        self.assertEqual(daily_direction(ps),1)
        ps[-1]['price']=89;self.assertEqual(daily_direction(ps),0)

if __name__=='__main__':unittest.main()
