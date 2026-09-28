"""Frozen PR #28 mechanics for the bakeoff suffix only.

Verbatim from rocket branch codex/crypto-strategy-research:
engine.py SHA ad7c6586a973b46ede17641f056b520f30126d50
execution.py SHA fb60ccbee9e5dd3098e8c7452840f6029d32941c

The only addition is `_fill_only` on a bar: the measured tape's last 1h open
had no closed range yet. That bar can fill a trigger already produced by a
closed hour, and it can gap through the stop at its open. It does not run
flip_step and it does not walk a high or a low. The live scan does not import
this module.
"""

import calendar
import math
from collections import defaultdict
from datetime import datetime, timezone

H = 3600000
D = 24 * H
W = 7 * D
MONDAY = 4 * D


def aggregate(bars, step, cutoff, offset=0):
    groups = defaultdict(list)
    for b in bars:
        start = (b["t"] - offset) // step * step + offset
        if b["t"] + H <= cutoff and start + step <= cutoff:
            groups[start].append(b)
    out = []
    for start, rs in sorted(groups.items()):
        if [b["t"] for b in rs] != list(range(start, start + step, H)):
            continue
        out.append(
            dict(
                t=start,
                o=rs[0]["o"],
                h=max(b["h"] for b in rs),
                l=min(b["l"] for b in rs),
                c=rs[-1]["c"],
            )
        )
    return out


def pivots(bars, width, step):
    out = []
    for i in range(width, len(bars) - width):
        rs = bars[i - width : i + width + 1]
        if any(b["t"] - a["t"] != step for a, b in zip(rs, rs[1:])):
            continue
        for side, key in [(1, "h"), (-1, "l")]:
            p = bars[i][key]
            if all(side * (p - b[key]) > 0 for j, b in enumerate(rs) if j != width):
                out.append(
                    dict(t=bars[i]["t"], available=bars[i + width]["t"] + step, side=side, price=p)
                )
    return out


def velocity(weeks):
    if len(weeks) < 9 or any(b["t"] - a["t"] != W for a, b in zip(weeks[-9:], weeks[-8:])):
        return None
    tr = [
        max(b["h"] - b["l"], abs(b["h"] - a["c"]), abs(b["l"] - a["c"]))
        for a, b in zip(weeks[-9:], weeks[-8:])
    ]
    atr = sum(tr) / 8
    return (weeks[-1]["c"] - weeks[-5]["c"]) / atr if atr else None


def daily_direction(ps):
    highs = [p for p in ps if p["side"] == 1]
    lows = [p for p in ps if p["side"] == -1]
    if len(highs) < 2 or len(lows) < 2:
        return None
    dh = highs[-1]["price"] - highs[-2]["price"]
    dl = lows[-1]["price"] - lows[-2]["price"]
    return 1 if dh > 0 and dl > 0 else -1 if dh < 0 and dl < 0 else 0


def impulses(daily):
    """As-of daily BOS state; pending terminal confirmation never backdates."""
    ps = pivots(daily, 3, D)
    state = None
    states = []
    for i, b in enumerate(daily):
        avail = [p for p in ps if p["available"] <= b["t"]]
        events = []
        for side in (1, -1):
            levels = [p for p in avail if p["side"] == side]
            if (
                i
                and levels
                and side * (b["c"] - levels[-1]["price"]) > 0
                and side * (daily[i - 1]["c"] - levels[-1]["price"]) <= 0
            ):
                events.append(side)
        if events:
            direction = events[-1]
            origins = [p for p in avail if p["side"] == -direction]
            if origins:
                origin = state["origin"] if state and state["direction"] == direction else origins[-1]["price"]
                ot = state["origin_t"] if state and state["direction"] == direction else origins[-1]["t"]
                terminal = b["h" if direction == 1 else "l"]
                if not state or state["direction"] != direction or direction * (terminal - state["terminal"]) > 0:
                    state = dict(
                        direction=direction,
                        origin=origin,
                        origin_t=ot,
                        terminal=terminal,
                        terminal_t=b["t"],
                        bos_time=b["t"] + D,
                        confirmed=False,
                    )
        if state:
            state = dict(state)
            direction = state["direction"]
            if direction * (b["c"] - state["origin"]) < 0:
                state = None
            elif b["t"] > state["terminal_t"] and not state["confirmed"]:
                if direction * (b["h" if direction == 1 else "l"] - state["terminal"]) > 0:
                    state["terminal_failed"] = True
                state["confirmed"] = not state.get("terminal_failed", False) and b["t"] >= state["terminal_t"] + 3 * D
        states.append(dict(state) if state else None)
    return states


def institutional(swing, origin, direction):
    unit = 10 ** (math.floor(math.log10(origin)) - 3)
    base = math.floor(swing / (100 * unit))
    levels = [(100 * k + n) * unit for k in range(base - 1, base + 2) for n in (0, 20, 50, 80)]
    return max(x for x in levels if x < swing) if direction == 1 else min(x for x in levels if x > swing)


def inside(price, zone):
    return zone[0] <= price <= zone[1]


def intersects(bar, zone):
    return bar["l"] <= zone[1] and bar["h"] >= zone[0]


def zone_candidates(h4, daily, weeks, leg, monthly_refs=()):
    d = leg["direction"]
    origin = leg["origin"]
    terminal = leg["terminal"]
    band = sorted([terminal + (origin - terminal) * r for r in (0.75, 0.86)])
    ps = pivots(h4, 2, 4 * H)
    out = []
    refs = list(monthly_refs)
    for rows in (daily, weeks):
        if rows:
            refs.extend([rows[-1]["o"], rows[-1]["c"]])
    for p in reversed(ps):
        if p["side"] != -d or not inside(p["price"], band):
            continue
        level = institutional(p["price"], origin, d)
        ben = sorted([p["price"], level])
        zone = [max(ben[0], band[0]), min(ben[1], band[1])]
        if zone[0] >= zone[1]:
            continue
        factors = ["swing", "institutional"]
        if any(inside(r, ben) for r in refs):
            factors.append("period_reference")
        if any(
            (d == 1 and a["h"] < c["l"] and max(a["h"], ben[0]) <= min(c["l"], ben[1]))
            or (d == -1 and c["h"] < a["l"] and max(c["h"], ben[0]) <= min(a["l"], ben[1]))
            for a, c in zip(h4, h4[2:])
        ):
            factors.append("fvg")
        touches = [q for q in ps if q["t"] < p["t"] and q["side"] == p["side"] and inside(q["price"], ben)]
        if len(touches) >= 2 and touches[-1]["t"] - touches[-2]["t"] > 4 * H:
            factors.append("prior_touches")
        out.append(dict(zone=zone, ben=ben, band=band, pivot=p, factors=factors))
    return out


def reaction(bar, zone, d):
    body = abs(bar["c"] - bar["o"])
    wick = min(bar["o"], bar["c"]) - bar["l"] if d == 1 else bar["h"] - max(bar["o"], bar["c"])
    return intersects(bar, zone) and d * (bar["c"] - bar["o"]) > 0 and wick >= body and d * (bar["c"] - sum(zone) / 2) > 0


def objectives(h4, daily, zone, d):
    edge = zone[1 if d == 1 else 0]
    prices = {
        p["price"]
        for p in pivots(h4, 2, 4 * H) + pivots(daily, 3, D)
        if p["side"] == d and d * (p["price"] - edge) > 0
    }
    return sorted(prices, reverse=d == -1)[:2]


def latest_stop(hours, d):
    ps = [p for p in pivots(hours, 2, H) if p["side"] == -d]
    return ps[-1]["price"] * (1 - d * 0.0001) if ps else None


def frame(hours, cutoff):
    hours = [b for b in hours if b["t"] + H <= cutoff]
    h4 = aggregate(hours, 4 * H, cutoff)
    daily = aggregate(hours, D, cutoff)
    weeks = aggregate(hours, W, cutoff, MONDAY)
    v = velocity(weeks)
    wd = None if v is None else 1 if v > 1.2 else -1 if v < -1.2 else 0
    dd = daily_direction(pivots(daily, 3, D))
    ls = impulses(daily)
    leg = ls[-1] if ls else None
    blockers = []
    if wd is None:
        blockers.append("weekly_warmup_unknown")
    elif wd == 0:
        blockers.append("weekly_neutral")
    if dd is None:
        blockers.append("daily_structure_unknown")
    elif dd == 0:
        blockers.append("daily_mixed")
    if wd and dd and wd != dd:
        blockers.append("weekly_daily_disagree")
    if not leg or not leg["confirmed"]:
        blockers.append("impulse_unavailable")
    d = leg["direction"] if leg else dd if dd else wd
    if leg and dd and leg["direction"] != dd:
        blockers.append("impulse_daily_disagree")
    month_groups = defaultdict(list)
    for b in daily:
        dt = datetime.fromtimestamp(b["t"] / 1000, timezone.utc)
        month_groups[(dt.year, dt.month)].append(b)
    refs = []
    for (y, m), bs in sorted(month_groups.items()):
        if len(bs) == calendar.monthrange(y, m)[1]:
            refs = [bs[0]["o"], bs[-1]["c"]]
    zs = zone_candidates(h4, daily, weeks, leg, refs) if leg and leg["confirmed"] else []
    z = zs[0] if zs else None
    if not z:
        blockers.append("zone_unavailable")
    elif len(z["factors"]) < 3:
        blockers.append("confluence_below_three")
    if not z or not h4 or not reaction(h4[-1], z["zone"], d):
        blockers.append("reaction_absent")
    targets = objectives(h4, daily, z["zone"], d) if z else []
    if len(targets) < 2:
        blockers.append("two_objectives_unavailable")
    stop = latest_stop(hours, d) if d in (1, -1) else None
    if stop is None:
        blockers.append("hourly_stop_unknown")
    return dict(
        time=cutoff,
        weekly_velocity=v,
        weekly_direction=wd,
        daily_direction=dd,
        direction=d,
        leg=leg,
        candidate=z,
        targets=targets,
        passive_stop=stop,
        blockers=blockers,
        context={"cot": "UNKNOWN", "macro": "UNKNOWN", "historical_spread": "UNKNOWN"},
        eligible=not blockers,
    )


def flip_step(state, bars, hypothesis):
    """Only call on closed hourly bars after admission. State can never use future pivots."""
    d = hypothesis["direction"]
    z = hypothesis["candidate"]["zone"]
    b = bars[-1]
    prior = [p for p in pivots(bars[:-1], 2, H) if p["available"] <= b["t"]]
    state = dict(state)
    adverse = [p for p in prior if p["side"] == -d]
    opposing = [p for p in prior if p["side"] == d and inside(p["price"], z)]
    if state.get("broken"):
        level = state["level"]
        if intersects(b, [level, level]) and d * (b["c"] - level) > 0 and inside(b["c"], z):
            stop = latest_stop(bars, d)
            if stop is not None:
                return dict(state, trigger=b["t"] + H, stop=stop)
    elif state.get("swept") and opposing:
        level = opposing[-1]["price"]
        if d * (b["c"] - level) > 0 and inside(b["c"], z):
            state.update(broken=b["t"] + H, level=level)
    elif adverse:
        p = adverse[-1]["price"]
        extreme = b["l" if d == 1 else "h"]
        if d * (extreme - p) < 0 and d * (b["c"] - p) > 0 and intersects(b, z):
            state["swept"] = b["t"] + H
    return state


def next_run(t):
    base = t // D * D
    return min(x for day in (base, base + D) for hour in (11, 17, 23) if (x := day + hour * H) >= t)


def execute_bar(position, bar, path, entry_limit=None):
    """Mutates a private position; no made-up ordering inside a chosen path."""
    p = position
    d = p["direction"]
    events = []
    step = bar.get("_step", H)
    vertices = [bar[k] for k in ("o", "l", "h", "c")] if path == "OLHC" else [bar[k] for k in ("o", "h", "l", "c")]

    def enter(price):
        p.update(
            entry=price,
            risk=d * (price - p["stop"]),
            remaining=1.0,
            entry_time=bar["t"],
            entry_time_bounds=[bar["t"], bar["t"] + step],
            exits=[],
            tp=0,
        )
        events.append("entry")

    def close(price, qty, reason):
        qty = min(qty, p["remaining"])
        p["remaining"] = max(0.0, p["remaining"] - qty)
        p["exits"].append(
            dict(
                price=price,
                quantity=qty,
                reason=reason,
                time=bar["t"] + step,
                time_bounds=[bar["t"], bar["t"] + step],
            )
        )
        events.append(reason)

    def barriers(price, at_open=False):
        if "entry" not in p or p["remaining"] <= 1e-12:
            return
        if d * (price - p["stop"]) <= 0:
            close(price if at_open else p["stop"], p["remaining"], "stop")
            return
        while p["tp"] < 2 and d * (price - p["targets"][p["tp"]]) >= 0:
            n = p["tp"]
            close(p["targets"][n], 0.8 if n == 0 else 0.1, "target" + str(n + 1))
            p["tp"] += 1

    if "entry" not in p and entry_limit is not None and d * (vertices[0] - entry_limit) <= 0:
        enter(vertices[0])
    barriers(vertices[0], True)
    for a, b in zip(vertices, vertices[1:]):
        if "entry" not in p and entry_limit is not None and min(a, b) <= entry_limit <= max(a, b):
            enter(entry_limit)
            a = entry_limit
        if "entry" not in p or p["remaining"] <= 1e-12:
            continue
        levels = [p["stop"]] + p["targets"][p["tp"] :]
        for level in sorted(set(x for x in levels if min(a, b) <= x <= max(a, b)), reverse=b < a):
            barriers(level)
        barriers(b)
    return events


def economics(p, funding):
    if "entry" not in p:
        return {}
    entry = p["entry"]
    risk = p["risk"]
    d = p["direction"]
    gross = sum(x["quantity"] * d * (x["price"] - entry) for x in p["exits"])
    buckets = {int(r["time"]) // H * H: float(r["fundingRate"]) for r in funding}
    start = p["entry_time"]
    end = p["end_time"]
    low = high = 0.0
    missing = []
    for t in range((start + H - 1) // H * H, end + 1, H):
        if t not in buckets:
            missing.append(t)
            continue
        before = sum(x["quantity"] for x in p["exits"] if x["time_bounds"][1] < t)
        through = sum(x["quantity"] for x in p["exits"] if x["time_bounds"][0] <= t)
        qmax = max(0, 1 - before)
        qmin = max(0, 1 - through)
        if t <= p["entry_time_bounds"][1]:
            qmin = 0
        r = d * buckets[t] * entry
        low += min(r * qmin, r * qmax)
        high += max(r * qmin, r * qmax)
    closed = p["remaining"] <= 1e-12
    result = dict(
        gross_realized_r=gross / risk,
        remaining=p["remaining"],
        funding_missing_hours=missing,
        funding_cost_bounds_r=[low / risk, high / risk],
        exposure_hours=(end - start) / H,
        completed=closed,
        net={},
    )
    for bps in (10, 20, 40):
        cost = entry * bps / 10000 * (0.5 + 0.5 * (1 - p["remaining"]))
        result["net"][str(bps)] = (
            None
            if missing or not closed
            else {
                "r_lower": (gross - cost - high) / risk,
                "r_upper": (gross - cost - low) / risk,
                "notional_lower": (gross - cost - high) / entry,
                "notional_upper": (gross - cost - low) / entry,
            }
        )
    return result


def simulate(hours, hypothesis, mode, path, funding, invalidations=(), finer=None):
    d = hypothesis["direction"]
    zone = hypothesis["candidate"]["zone"]
    targets = hypothesis["targets"]
    t = hypothesis["time"]
    expiry = t + 8 * D
    p = dict(direction=d, stop=hypothesis["passive_stop"], targets=targets, remaining=0.0)
    out = dict(
        time=t,
        mode=mode,
        path=path,
        status="pending",
        events=[],
        expiry=expiry,
        origin=hypothesis["leg"]["origin"],
        zone=zone,
        targets=targets,
    )
    state = {}
    pending_trigger = None
    pending_thesis = False
    indexes = [i for i, b in enumerate(hours) if b["t"] >= t]
    limit = zone[1 if d == 1 else 0]
    for i in indexes:
        b = hours[i]
        now = b["t"]
        out["end_time"] = now + H
        if "entry" not in p and now >= expiry:
            out.update(status="expired", end_time=expiry)
            break
        if "entry" not in p and (now in invalidations or d * (b["o"] - out["origin"]) < 0):
            out.update(status="invalidated_before_entry", end_time=now)
            break
        if pending_thesis and "entry" in p:
            p["exits"].append(
                dict(
                    price=b["o"],
                    quantity=p["remaining"],
                    reason="thesis_exit",
                    time=now,
                    time_bounds=[now, now],
                )
            )
            p["remaining"] = 0.0
            out.update(status="closed", end_time=now)
            break
        enter_limit = None
        if "entry" not in p:
            if mode == "flip" and pending_trigger:
                price = b["o"]
                p["stop"] = pending_trigger["stop"]
            elif mode == "passive":
                if not (b["l"] <= limit if d == 1 else b["h"] >= limit):
                    price = None
                else:
                    price = b["o"] if d * (b["o"] - limit) <= 0 else limit
            else:
                price = None
            if price is not None:
                risk = d * (price - p["stop"])
                if not inside(price, zone) or risk <= 0 or d * (targets[0] - price) < risk:
                    out.update(status="entry_risk_or_zone_rejected")
                    break
                if mode == "flip":
                    p.update(
                        entry=price,
                        risk=risk,
                        remaining=1.0,
                        entry_time=now,
                        entry_time_bounds=[now, now],
                        exits=[],
                        tp=0,
                    )
                    out["events"].append(dict(time=now, event="entry_next_open"))
                else:
                    enter_limit = limit
        subbars = (finer or {}).get(now, [b])
        if len(subbars) > 1:
            out["finer_hours_used"] = out.get("finer_hours_used", 0) + 1
        for sb in subbars:
            events = execute_bar(p, sb, path, enter_limit)
            for event in events:
                out["events"].append(dict(time_bounds=[sb["t"], sb["t"] + sb.get("_step", H)], event=event))
            if "entry" in p and p["remaining"] <= 1e-12:
                out["end_time"] = sb["t"] + sb.get("_step", H)
                break
        if "entry" in p:
            if p["remaining"] <= 1e-12:
                out["status"] = "closed"
                break
            if p["tp"] >= 2:
                stop = latest_stop(hours[: i + 1], d)
                if stop is not None and d * (stop - p["stop"]) > 0 and d * (b["c"] - stop) > 0:
                    p["stop"] = stop
            pending_thesis = now + H in invalidations or ((now + H) % (4 * H) == 0 and d * (b["c"] - out["origin"]) < 0)
        else:
            if (now + H) % (4 * H) == 0 and d * (b["c"] - out["origin"]) < 0:
                out["status"] = "invalidated_before_entry"
                break
            if mode == "flip" and not b.get("_fill_only"):
                newer = flip_step(state, hours[: i + 1], hypothesis)
                for event in ("swept", "broken", "trigger"):
                    if event in newer and event not in state:
                        out["events"].append(dict(time=now + H, event=event))
                state = newer
                if state.get("trigger"):
                    pending_trigger = state
                    out["trigger_time"] = state["trigger"]
    else:
        out["status"] = "unresolved_position" if "entry" in p else "unresolved_pending"
    out.setdefault("end_time", t)
    if "entry" in p:
        out.update(p)
        out["end_time"] = out.get("end_time", t)
        out["initial_stop"] = out["entry"] - d * out["risk"]
        out["economics"] = economics(out, funding)
        deadline = out.get("trigger_time", out["entry_time"])
        out["scheduled_observable"] = next_run(t) <= deadline
        out["next_scheduled_run"] = next_run(t)
    return out


def compute_frames(hours):
    times = [b["t"] + H for b in hours if (b["t"] + H) % (4 * H) == 0 and not b.get("_fill_only")]
    return [dict(frame(hours, t), index=i) for i, t in enumerate(times)]
