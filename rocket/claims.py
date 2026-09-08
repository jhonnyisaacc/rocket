"""Deterministic exact-measure claims. Ambiguity is an output, never a proxy."""

import calendar
import re
import unicodedata
from datetime import date, timedelta


def plain(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


# Ordered longest/specific first. Spot and futures are distinct instruments.
MEASURES = (
    ("CORE_CPI_YOY", r"(?:core cpi|ipc subyacente|cpi subyacente).*(?:yoy|interanual|year.over.year)"),
    ("CPI_YOY", r"(?:cpi|ipc).*(?:yoy|interanual|year.over.year)"),
    ("CORE_CPI", r"core cpi|ipc subyacente|cpi subyacente"),
    ("CPI", r"\bcpi\b|\bipc\b"),
    ("DXY", r"\bdxy\b|dollar index|indice dolar"),
    ("US10Y", r"10.year (?:yield|treasury)|10y yield|rendimiento.*10 anos|bono.*10 anos"),
    ("WALCL", r"fed balance sheet|balance de la fed|balance de la reserva federal"),
    ("TGA", r"\btga\b"), ("RRP", r"\brrp\b|reverse repo"),
    ("NET_LIQUIDITY", r"(?:walcl|fed balance sheet|balance de la fed)\s*(?:-|minus|menos)\s*tga\s*(?:-|minus|menos)\s*rrp"),
    ("BTC_USD", r"\bbtc\b|\bbitcoin\b"),
    ("SP500", r"s&p\s*500|sp500|s p 500"),
    ("NASDAQ_COMPOSITE", r"nasdaq composite|nasdaq compuesto"),
    ("GOLD_FUTURES", r"gold futures|futuros (?:del? )?oro|\bgc=f\b"),
    ("COPPER_FUTURES", r"copper futures|futuros (?:del? )?cobre|\bhg=f\b"),
    ("GOLD_SPOT", r"\bgold\b|\boro\b|\bxau\b"),
    ("COPPER_UNSPECIFIED", r"\bcopper\b|\bcobre\b"),
)


def shift_month(day, months):
    number = day.year * 12 + day.month - 1 + months
    year, month = divmod(number, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def parse_claim(text, *, claim_id, claim_date):
    normalized = plain(text)
    measures = []
    for measure, pattern in MEASURES:
        if re.search(pattern, normalized):
            if measure == "CPI_YOY" and "CORE_CPI_YOY" in measures:
                continue
            if measure in {"CPI", "CORE_CPI"} and any("CPI" in m for m in measures):
                continue
            if measure == "GOLD_SPOT" and "GOLD_FUTURES" in measures or measure == "COPPER_UNSPECIFIED" and "COPPER_FUTURES" in measures:
                continue
            measures.append(measure)
    if "NET_LIQUIDITY" in measures:
        measures = [m for m in measures if m not in {"WALCL", "TGA", "RRP"}]
    # CPI without a specified rate or index basis is not safely interchangeable
    # with its price index, monthly rate, or year-over-year rate.
    if measures in (["CPI"], ["CORE_CPI"]) and not re.search(r"\b(index|indice)\b", normalized):
        measures = []
    forecast = bool(re.search(r"\b(?:will|expect|forecast|next|subira|bajara|caera|crecera|espero|preve|proximo|proxima)\b", normalized))
    forecast = forecast and not re.search(r"[?¿]", normalized)
    causal = bool(re.search(r"\b(?:because|causes?|porque|debido a|provoca|por tanto)\b", normalized))
    hypothesis = bool(re.search(r"\b(?:could|might|may|podria|quiza|probablemente|hipotesis|if|si)\b", normalized))
    up = bool(re.search(r"\b(?:rise|rises|rising|rose|increase|increased|increasing|sube|subiendo|subio|aumenta|aumentando|aumento)\b", normalized))
    down = bool(re.search(r"\b(?:fall|falls|falling|fell|decline|declined|decreasing|baja|bajando|bajo|cae|cayo|cayendo)\b", normalized))
    negated = bool(re.search(r"\b(?:not|no|never|nunca)\b", normalized))
    comparator = re.search(r"(?:above|below|por encima de|por debajo de|superior a|inferior a)\s*\$?([\d,.]+)\s*(%)?", normalized)
    level = re.search(r"(?:is at|stands at|esta en|se situa en)\s*\$?([\d,.]+)\s*(%)?", normalized)
    kind = "FORECAST" if forecast else "CAUSAL" if causal else "HYPOTHESIS" if hypothesis else "LEVEL" if comparator or level else "CHANGE" if up != down else "COMMENTARY"
    if not forecast and not causal and (re.search(r"\b(but|although|however|pero|aunque)\b", normalized)
        or len(re.findall(r"\b(above|below|encima|debajo|superior|inferior)\b", normalized)) > 1):
        kind = "COMMENTARY"
    operator, value = None, None
    if comparator or level:
        match = comparator or level
        number = match[1].rstrip(".,")
        # A single three-digit group can be a decimal or thousands separator.
        ambiguous_number = bool(re.search(r"[.,]\d{3}$", number))
        try:
            value = float(number.replace(",", ".")) if not ambiguous_number and number.count(".") + number.count(",") <= 1 else None
        except ValueError:
            value = None
        operator = "above" if comparator and re.search(r"above|encima|superior", comparator[0]) else "below" if comparator else "at"
    end, start, window = claim_date, None, None
    if re.search(r"this week|esta semana", normalized):
        start, window = claim_date - timedelta(days=claim_date.weekday() + 1), "this week"
    elif re.search(r"last month|ultimo mes", normalized):
        start, window = shift_month(claim_date, -1), "last month"
    elif re.search(r"year.over.year|interanual|\byoy\b", normalized) and not any(m.endswith("YOY") for m in measures):
        start, window = shift_month(claim_date, -12), "year over year"
    elif re.search(r"today|hoy", normalized):
        start, window = claim_date - timedelta(days=1), "today"
    since = re.search(r"(?:since|desde)\s+(\d{4}-\d{2}-\d{2})", normalized)
    if since:
        try:
            start, window = date.fromisoformat(since[1]), since[0]
        except ValueError:
            pass
    months = {plain(calendar.month_name[i]): i for i in range(1, 13)}
    months.update(dict(zip(("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"), range(1, 13), strict=True)))
    since_month = re.search(r"(?:since|desde)\s+(\w+)(?:\s+(\d{4}))?", normalized)
    if since_month and since_month[1] in months:
        month = months[since_month[1]]
        year = int(since_month[2]) if since_month[2] else claim_date.year - int(month > claim_date.month)
        start, window = date(year, month, 1), since_month[0]
    historical = re.search(r"(?:on|el|as of|a fecha de)\s+(\d{4}-\d{2}-\d{2})", normalized)
    if historical:
        try:
            end = date.fromisoformat(historical[1])
        except ValueError:
            pass
    horizon = re.search(r"(?:by|para|hasta)\s+(\d{4}-\d{2}-\d{2})|(?:next|proxim[oa])\s+(?:week|month|year|semana|mes|ano)", normalized)
    return {"claim_id": claim_id, "claim": text, "claim_date": claim_date.isoformat(),
            "measures": measures, "exact_measure": measures[0] if len(measures) == 1 else None,
            "kind": kind, "direction": "up" if up and not down else "down" if down and not up else None,
            "negated": negated, "operator": operator, "level": value,
            "level_unit": "percent" if (comparator or level) and (comparator or level)[2] else None,
            "timeframe": window, "window_start": start.isoformat() if start else None,
            "window_end": end.isoformat(), "historical": historical is not None,
            "horizon": horizon[0] if horizon else None,
            "causality": "UNESTABLISHED" if causal else None,
            "status": "FORECAST" if forecast else "UNVERIFIED", "evidence": [],
            "current_evidence": "insufficient" if forecast else None,
            "interpretation": "Exact measure, semantics, or required comparison window is not established."}


def evaluate_claim(claim, observations):
    """Observations are already PIT/source checked by acquisition."""
    out = dict(claim)
    if not claim["exact_measure"] or claim["kind"] in {"COMMENTARY", "HYPOTHESIS", "CAUSAL", "FORECAST"}:
        return out
    end = date.fromisoformat(claim["window_end"])
    eligible = sorted((date.fromisoformat(r["date"][:10]), r["value"]) for r in observations if date.fromisoformat(r["date"][:10]) <= end)
    if not eligible:
        return out
    day, latest = eligible[-1]
    # Date-specific levels require that observation, not a conveniently nearby print.
    if claim["historical"] and day != end:
        return out
    success = None
    prior = None
    if claim["kind"] == "LEVEL" and claim["level"] is not None:
        success = latest > claim["level"] if claim["operator"] == "above" else latest < claim["level"] if claim["operator"] == "below" else abs(latest - claim["level"]) < 1e-8
    elif claim["kind"] == "CHANGE" and claim["window_start"]:
        start = date.fromisoformat(claim["window_start"])
        before = [(d, v) for d, v in eligible if d <= start]
        if not before or day <= start:
            return out
        prior_day, prior = before[-1]
        # At most one trading weekend; monthly series need explicit monthly endpoints.
        if (start - prior_day).days > 4:
            return out
        success = latest > prior if claim["direction"] == "up" else latest < prior
    if success is None:
        return out
    if claim["negated"]:
        success = not success
    out.update(status="VERIFIED" if success else "CONTRADICTED", observed_value=latest,
               prior_value=prior, observation_date=day.isoformat(),
               interpretation="The exact observed measure agrees with the factual assertion." if success else "The exact observed measure contradicts the factual assertion.")
    return out
