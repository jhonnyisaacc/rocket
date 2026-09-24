"""Deterministic historical-state approximation; never submits transactions.

Run with local immutable captures. There is no network fallback in this module.
Required accounts except the new token ATA are assumed pre-existing. No cashback
claim or rent refund is credited. Historical later states do NOT include our buy.
"""
import csv
import hashlib
import json
import math
from fractions import Fraction
from pilot_capture import BASE, OUT, stable, digest
from pilot_decode import load_evidence, OLD, instructions, VERSION as DECODER_VERSION
from pilot_model import buy_exact_input, sell, post_state, after_buy, meets_slippage, VERSION as MODEL_VERSION

JITO = {
 '96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5','HFqU5x63VTqvQss8hp11i4wVV8bD44PvwucfZ2bU7gRe',
 'Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY','ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49',
 'DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh','ADuUkR4vqLUMWXxW9gh6D6L8pMSawimctcNZ5pGwDcEt',
 'DttWaMuVvTiduZRnguLF7jNxTgiMBZ1hyAumKUiL2KRL','3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnizKZ6jT'}
ANCHORS = {'loss':1782328096, 'winner':1782326648}
OWNER = '789sBYAGntSyAPoS4ZH3zo3SUFuv1jeAjPeaq7muVany'
TOKEN_ACCOUNT_DEPOSIT = 2074080
NEW_ACCUMULATOR_DEPOSIT = 1844400  # Five independently observed 137-byte creations.


def coverage_intervals(evidence, reserve):
    """Only a terminated cursor chain establishes provider-reported coverage."""
    lookup = {}
    for row in evidence['inventory']:
        capture = json.loads((BASE/row['path']).read_text())
        lookup[stable(capture['request']['params'])] = capture
    result=[]
    for row in evidence['inventory']:
        address, options = row['request']['params']
        if address != reserve or 'paginationToken' in options:
            continue
        cursor = lookup[stable([address,options])]
        visited=set();complete=False
        while True:
            key=stable(cursor['request']['params'])
            if key in visited:
                break
            visited.add(key)
            token=cursor['response']['result'].get('paginationToken')
            if not token:
                complete=True;break
            next_options=dict(options,paginationToken=token)
            cursor=lookup.get(stable([address,next_options]))
            if cursor is None:
                break
        bounds=options['filters']['blockTime']
        result.append(dict(start=bounds['gte'],end=bounds['lt'],complete=complete,pages=len(visited)))
    return sorted(result,key=lambda x:(x['start'],x['end']))


def covered(intervals,start,end):
    cursor=start
    for interval in sorted(intervals,key=lambda x:x['start']):
        if not interval['complete'] or interval['end'] <= cursor:
            continue
        if interval['start']>cursor:
            break
        cursor=max(cursor,interval['end'])
        if cursor>end:
            return True
    return False


def state_at(events, target, start, intervals, exclusions):
    if target<start:
        raise ValueError('Target precedes source event')
    if not covered(intervals,start,target):
        raise ValueError('Incomplete cursor-verified state interval')
    if any(not isinstance(x.get('event_time'),int) or start <= x['event_time'] <= target for x in exclusions):
        raise ValueError('Unresolved transaction or truncated logs in state path')
    candidates=[e for e in events if e['event_time']<=target]
    if not candidates:
        raise ValueError('Missing state before target')
    # Timestamp-resolution convention: after ALL cached ordered transactions in
    # the final slot whose block time is <= target. Not measured bot availability.
    return candidates[-1]


def observed_costs(evidence, mint):
    relevant={e['signature'] for e in evidence['events'] if e['mint']==mint}
    samples=[];seen=set()
    for row in evidence['inventory']:
        capture=json.loads((BASE/row['path']).read_text())
        for raw in capture['response']['result']['data']:
            sig=raw['transaction']['signatures'][0]
            if sig not in relevant or sig in seen:
                continue
            seen.add(sig)
            tips=sum(i['parsed']['info']['lamports'] for _,_,i in instructions(raw)
                     if i.get('program')=='system' and i.get('parsed',{}).get('type')=='transfer'
                     and i['parsed']['info'].get('destination') in JITO)
            samples.append(dict(signature=sig,network_fee=raw['meta']['fee'],recognized_jito_tip=tips,
                                total=raw['meta']['fee']+tips,source=row['path']))
    samples.sort(key=lambda x:(x['total'],x['signature']))
    return {name:dict(samples[max(0,math.ceil(len(samples)*q)-1)],quantile=q,sample_size=len(samples))
            for name,q in [('low',0),('median',0.5),('high',0.95)]}


def simulate(evidence, label, mint, size, delay, frozen):
    rows=[e for e in evidence['events'] if e['mint']==mint]
    anchor=next((e for e in rows if e['event_time']==ANCHORS[label] and e['user']==OWNER and e['is_buy']),None)
    t0=ANCHORS[label];entry_time=t0+delay
    decision_time=entry_time+frozen['holding_seconds_after_entry'];exit_time=decision_time+delay
    result=dict(case=label,mint=mint,size_lamports=size,delay_seconds=delay,status='unavailable',
                reason=None,net_modeled_lamports=None,source_event_time=t0,source_available_at=None,
                modeled_signal_available_at=t0,
                modeled_availability_assumption='Scenario only: decision at anchor block time; not measured feed receipt or finality',
                modeled_entry_time=entry_time,modeled_exit_decision_time=decision_time,modeled_exit_time=exit_time,
                anchor_signature=anchor['signature'] if anchor else None,decoder_version=DECODER_VERSION,model_version=MODEL_VERSION,
                simulation_kind='historical-state execution approximation',
                sample_role='known-outcome development fixture',economic_costs=None)
    if anchor is None:
        result['reason']='Missing verified source buy'
        return result
    intervals=coverage_intervals(evidence,anchor['reserve'])
    exclusions=[e for e in evidence['exclusions'] if e.get('source') in {r['path'] for r in evidence['inventory'] if r['request']['params'][0]==anchor['reserve']}]
    for event in rows:
        checks=event['checks']
        if not all(checks.get(k,False) for k in ('quote_matches','fees_match','protocol_destination_matches','buyback_destination_matches')) or checks.get('cashback_treatment')=='unresolved_destination_accounting':
            exclusions.append(dict(event_time=event['event_time'],reason='Unvalidated quote or fee destination accounting'))
    for transition in evidence['transitions']:
        if transition['mint']==mint and not transition['pass_all']:
            next_event=next(e for e in rows if e['signature']==transition['next'])
            exclusions.append(dict(event_time=next_event['event_time'],reason='Independent state continuity failure'))
    costs=observed_costs(evidence,mint)
    result['observed_cost_scenarios']=costs
    # Conservative cash allocation: enough to pay entry+exit network/tip costs
    # before receiving sale proceeds, plus retained ATA funding, no rent refund.
    result['cash_required_lamports']={name:size+TOKEN_ACCOUNT_DEPOSIT+2*c['total'] for name,c in costs.items()}
    result['cash_required_if_new_accumulator_lamports']={name:value+NEW_ACCUMULATOR_DEPOSIT for name,value in result['cash_required_lamports'].items()}
    result['deposit_locked_lamports']=TOKEN_ACCOUNT_DEPOSIT
    result['platform_fee_lamports']=0
    result['unpriced_components']=['unobserved inclusion/MEV costs; no inclusion probability model',
        'non-Jito routing/service transfers excluded under direct-program scenario',
        'other protocol account setup/top-ups assumed unnecessary; new accumulator deposit shown separately',
        'off-chain infrastructure costs']
    result['exit_coverage_supported']=covered(intervals,t0,exit_time) and not any(not isinstance(x.get('event_time'),int) or t0<=x['event_time']<=exit_time for x in exclusions)
    try:
        expected=buy_exact_input(post_state(anchor),size)
        entry_event=state_at(rows,entry_time,t0,intervals,exclusions)
        entry=buy_exact_input(post_state(entry_event),size)
        result.update(expected_entry_tokens=expected['tokens'],entry_quote_tokens=entry['tokens'],
                      entry_state_signature=entry_event['signature'],entry_state_time=entry_event['event_time'],
                      entry_state_age_seconds=entry_time-entry_event['event_time'],entry_quote=entry)
        # Naive comparator only: same average all-in price as the leader, no
        # delay and no size-specific impact. Do not label it an executable fill.
        leader_spend=anchor['sol_amount']+anchor['fee']+anchor['creator_fee']+anchor['cashback']
        result['leader_fill_shortcut_tokens']=size*anchor['token_amount']//leader_spend
        result['entry_shortcut_token_difference']=entry['tokens']-result['leader_fill_shortcut_tokens']
        before=post_state(entry_event);after=after_buy(before,entry)
        impact=Fraction(after.sol*before.tokens,after.tokens*before.sol)-1
        result['immediate_entry_price_impact_bps']=float(impact*10000)
        if not meets_slippage(expected['tokens'],entry['tokens'],frozen['slippage_bps']):
            result.update(status='rejected',reason='Entry output breaches fixed 2% slippage floor',
                          rejected_stage='entry',entry_filled=False,
                          attempted_failure_network_cost_lamports={n:c['network_fee'] for n,c in costs.items()},
                          rejected_cost_note='No trade PnL. If attempted on-chain, network fee remains; atomic transfers/deposits revert. Unlanded/preflight rejection has no chain fee.')
            return result
        result['entry_filled']=True
        decision=state_at(rows,decision_time,t0,intervals,exclusions)
        exit_event=state_at(rows,exit_time,t0,intervals,exclusions)
        expected_exit=sell(post_state(decision),entry['tokens'])
        exit_quote=sell(post_state(exit_event),entry['tokens'])
        result.update(exit_state_signature=exit_event['signature'],exit_state_time=exit_event['event_time'],
                      exit_state_age_seconds=exit_time-exit_event['event_time'],exit_quote=exit_quote,
                      expected_exit_cash=expected_exit['cash'])
        exit_state=post_state(exit_event)
        result['immediate_exit_price_impact_bps']=float((1-Fraction((exit_state.sol-exit_quote['gross'])*exit_state.tokens,
                                                                           (exit_state.tokens+exit_quote['tokens'])*exit_state.sol))*10000)
        if not meets_slippage(expected_exit['cash'],exit_quote['cash'],frozen['slippage_bps']):
            result.update(status='rejected',reason='Exit output breaches fixed 2% slippage floor',
                          rejected_stage='exit',remaining_tokens=entry['tokens'],
                          rejected_cost_note='Entry inventory remains; no realized round-trip return or invented fallback exit.')
            return result
        gross_outcome=exit_quote['cash']-entry['cash']
        outcomes={name:gross_outcome-2*c['total'] for name,c in costs.items()}
        result.update(status='simulated',reason='Conditional direct-program execution at historical states',
                      economic_costs={name:2*c['total'] for name,c in costs.items()},
                      net_modeled_lamports=outcomes['median'],net_scenarios_lamports=outcomes,
                      wallet_cash_change_lamports={name:value-TOKEN_ACCOUNT_DEPOSIT for name,value in outcomes.items()},
                      cashback_accrued_not_realized_lamports=entry['fees']['cashback']+exit_quote['fees']['cashback'],
                      protocol_and_creator_and_cashback_charged_lamports=entry['fees']['charged']+exit_quote['fees']['charged'],
                      modeled_return_on_trade_budget_bps=outcomes['median']*10000/size)
        shortcut_tokens=result['leader_fill_shortcut_tokens']
        shortcut_exit=sell(post_state(exit_event),shortcut_tokens)
        result['leader_shortcut_same_exit_net_lamports']=shortcut_exit['cash']-size-2*costs['median']['total']
    except (ValueError,StopIteration) as exc:
        result.update(status='unavailable',reason=str(exc) or 'Missing anchor state')
    return result


def build_report():
    frozen=json.loads((BASE/'session_20260921_manifest.json').read_text())
    evidence=load_evidence()
    results=[simulate(evidence,label,mint,size,delay,frozen)
             for label,mint in frozen['fixtures'].items() for size in frozen['sizes_lamports'] for delay in frozen['delays_seconds']]
    ledger=[json.loads(x) for x in (OUT/'credits.jsonl').read_text().splitlines()]
    return dict(edge='NO_EDGE_VALIDATED',execution_enabled=False,automation='PAUSED',
                frozen_experiment_sha256=digest(frozen),results=results,
                evidence_inventory=evidence['inventory'],
                decoded_evidence_reference='data/session-2026-09-21/decoded_evidence.json',
                estimated_helius_credits=sum(x['reserved_credits'] for x in ledger),actual_provider_billing=None,
                successful_capture_credit_estimate=sum(x['reserved_credits'] for x in ledger if (OUT/(x['request_key']+'.json')).exists()),
                unresolved_or_rejected_reservations=[x for x in ledger if not (OUT/(x['request_key']+'.json')).exists()],
                implementation_sha256={name:hashlib.sha256((BASE/name).read_bytes()).hexdigest()
                                       for name in ('pilot_capture.py','pilot_decode.py','pilot_model.py','pilot_replay.py','pilot_discovery.py','pilot_validate.py')},
                credit_reservations=len(ledger),unique_transactions=evidence['unique_transactions'],
                decoded_events=len(evidence['events']),failed_transactions=len(evidence['failed']),
                exclusions=evidence['exclusions'],continuity_failures=[t for t in evidence['transitions'] if not t['pass_all']],
                coverage={label:coverage_intervals(evidence,json.loads((OLD/(source+'.json')).read_text())['request']['params'][0])
                          for label,source in [('loss','losing_cycle_market'),('winner','winner_entry_curve')]},
                assumptions=['Block-time delays are hypothetical, not observed feed latency.',
                             'End-of-timestamp ordered snapshot convention; available_at stays null.',
                             'Own immediate entry/exit impact included; historical future states and other traders are not counterfactually recomputed.',
                             'Protocol 95bps plus redirected creator cashback 30bps; buyback redistributes half of protocol fee.',
                             'No cashback claim or deposit refund; direct-program path has no platform service fee.',
                             'Observed network+recognized Jito cost quantiles applied per leg, not guarantees of inclusion.',
                             'No retry or fallback exit; rejected exits leave inventory; no return for unavailable or rejected cases.'])


def write_report(report):
    (OUT/'pilot_results.json').write_text(json.dumps(report,indent=2)+'\n')
    fields=['case','size_lamports','delay_seconds','status','reason','net_modeled_lamports','entry_quote_tokens','leader_fill_shortcut_tokens','exit_coverage_supported']
    with (OUT/'pilot_results.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(report['results'])


def main():
    report=build_report()
    write_report(report)
    fields=['case','size_lamports','delay_seconds','status','reason','net_modeled_lamports','entry_quote_tokens','leader_fill_shortcut_tokens','exit_coverage_supported']
    for result in report['results']:
        print(json.dumps({k:result.get(k) for k in fields}))
    print('estimated_credits',report['estimated_helius_credits'])


if __name__=='__main__':
    main()
