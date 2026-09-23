"""Regression tests using cached evidence only; zero network calls."""
import copy
import json
import unittest
from decode_cached_history import ROOT, decode
from reconcile_native_cashflows import reconcile
from decimal import Decimal
from verify_reserve_pairs import inspect
from audit_account_deposits import inspect as inspect_deposits
from decode_curve_state_events import events as curve_events, decode as decode_event

OWNER = '2heJbC32Tpfcb3nbUb5ER61K11FGZVfVGtVnDm6LDogF'
USDC = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
USELESS = 'Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk'

class EvidenceTests(unittest.TestCase):
    def test_curve_event_prefix_and_reverted_exclusion(self):
        capture=json.loads((ROOT/'losing_cycle_market.json').read_text())
        decoded=[e for r in capture['response']['result']['data'] for e in curve_events(r)]
        self.assertEqual(len(decoded),69)
        self.assertTrue(all(e['virtual_sol_reserves']>0 and e['virtual_token_reserves']>0 for e in decoded))
        for r in capture['response']['result']['data']:
            if r['meta']['err'] is not None:self.assertEqual(curve_events(r),[])
        with self.assertRaises(ValueError):decode_event(bytes([189,219,127,211,78,230,97,238]))

    def test_curve_rounding_is_instruction_specific(self):
        for name in ('losing_cycle_market','winner_entry_curve'):
            c=json.loads((ROOT/(name+'.json')).read_text())
            for raw in c['response']['result']['data']:
                for e in curve_events(raw):
                    sol,t=e['sol_amount'],e['token_amount']
                    expected=(e['virtual_sol_reserves']-sol)*t//e['virtual_token_reserves']+1 if e['is_buy'] else (e['virtual_sol_reserves']+sol)*t//e['virtual_token_reserves']
                    self.assertEqual(sol-expected,1 if e['ix_name'] in ('buy_exact_quote_in','buy_exact_sol_in') else 0)
                    self.assertEqual(e['fee'],(sol*e['fee_basis_points']+9999)//10000)

    def test_creation_funding_is_not_all_retained(self):
        capture=json.loads((ROOT/'historical_cohort_sample.json').read_text())
        rows=[v for r in capture['response']['result']['data'] for v in inspect_deposits(r,capture['address'])]
        transient=[r for r in rows if r['classification']=='closed_or_zero_at_end']
        surviving=[r for r in rows if r['classification']=='surviving_owner_token_account']
        self.assertEqual(len(transient),9)
        self.assertEqual(sum(r['funding_lamports'] for r in transient),15816080)
        self.assertEqual(len(surviving),12)
        self.assertEqual(sum(r['funding_lamports'] for r in surviving),24888960)

    def test_reserve_pairs_include_wrapped_sol(self):
        capture=json.loads((ROOT/'historical_cohort_sample.json').read_text())
        rows=[v for r in capture['response']['result']['data'] if (v:=inspect(r,capture['address'])) is not None]
        self.assertEqual(len(rows),55)
        self.assertEqual(sum(r['reserve_in_pump_instruction'] for r in rows),49)
        self.assertEqual(sum(r['reserve_in_amm_instruction'] for r in rows),6)
        self.assertTrue(all(r['quote_direction_pass'] and r['transaction_conserves_lamports'] for r in rows))
        amm=[r for r in rows if r['reserve_in_amm_instruction']]
        self.assertTrue(all(r['reserve_native_delta_lamports']==0 and r['reserve_wsol_delta_raw']!=0 for r in amm))

    def test_manual_adjudications(self):
        evidence=json.loads((ROOT.parent/'fomo-fill-adjudications.json').read_text())
        for fill in evidence['fills']:
            capture=json.loads((ROOT.parent/fill['cache']).read_text())
            raw=next(r for r in capture['response']['result']['data'] if r['transaction']['signatures'][0]==fill['signature'])
            row=decode(raw,evidence['owner'])
            self.assertIsNone(raw['meta']['err'])
            self.assertEqual(row['block_time'],fill['block_time'])
            self.assertTrue(row['owner_is_signer'])
            deltas={d['mint']:d['raw_delta'] for d in row['token_deltas']}
            self.assertEqual(deltas[evidence['mint']],fill['token_credit_raw'])
            self.assertEqual(deltas[evidence['quote_mint']],-fill['quote_debit_raw'])
            displayed=(Decimal(fill['quote_debit_raw']-sum(fill['separate_quote_transfers_raw']))/Decimal(1000000)).quantize(Decimal('0.01'))
            self.assertEqual(displayed,Decimal(fill['ui_buy_usd']))

    def test_failed_instructions_not_counted_as_transfers(self):
        capture=json.loads((ROOT/'historical_cohort_sample.json').read_text())
        failures=[r for r in capture['response']['result']['data'] if r['meta']['err'] is not None]
        self.assertEqual(len(failures),18)
        for raw in failures:
            row=reconcile(raw,capture['address'])
            self.assertEqual(row['parsed_native_movements'],[])
            self.assertEqual(row['unexplained_native_lamports'],0)

    def test_two_fills_and_no_mutation(self):
        for label, stamp, debit, credit in [('aug30',1788102082,50000000000,755233667715),
                                          ('aug25',1787690704,17675440000,284217750173)]:
            capture=json.loads((ROOT/('unipcs_useless_'+label+'.json')).read_text())
            raw=next(r for r in capture['response']['result']['data'] if r['blockTime']==stamp)
            before=copy.deepcopy(raw)
            row=decode(raw,OWNER)
            self.assertEqual(raw,before)
            self.assertTrue(row['owner_is_signer'])
            self.assertNotEqual(row['fee_payer'],OWNER)
            amounts={d['mint']:d['raw_delta'] for d in row['token_deltas']}
            self.assertEqual(amounts,{USDC:-debit,USELESS:credit})
            raw['meta']['err']={'InstructionError':[0,'Custom']}
            self.assertEqual(decode(raw,OWNER)['category'],'failed')

    def test_receipts_are_not_buys(self):
        capture=json.loads((ROOT/'fomo_unipcs_candidate.json').read_text())
        for raw in capture['response']['result']['data']:
            row=decode(raw,OWNER)
            self.assertEqual(row['category'],'token_inflow_only')
            self.assertFalse(row['verified_trade'])

    def test_failed_sell_cost_retained(self):
        report=json.loads((ROOT/'observed_cycle_audit.json').read_text())
        row=next(g for g in report['mint_groups'] if g['mint']=='435CfmvrJ4QtkVv4cZ1TbUa7rzrKKjvQJLMnvhTCpump')
        self.assertEqual(row['failed_attempts'],1)
        self.assertEqual(row['net_raw_tokens'],0)
        self.assertEqual(row['observed_native_cashflow_lamports'],-35471988)
        self.assertEqual(row['elapsed_seconds'],61)

if __name__=='__main__':
    unittest.main()
