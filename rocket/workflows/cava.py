"""Cava RSS → transcript → claims → FRED corroboration. Optional overlay only."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

from rocket.models import (
    Evidence,
    EvidenceKind,
    Mode,
    OperationalReport,
    OperationalStatus,
    Provenance,
    ProviderHealth,
    ReasonCode,
    ResearchReason,
    ResearchResult,
    ResearchStatus,
)
from rocket.providers.fred import _record_date, _record_value, fetch_series
from rocket.providers.supadata import Transcript, TranscriptProvider, TranscriptUnavailable
from rocket.store import ResearchStore

CAVA_CHANNEL_ID = "UCvCCLJkQpRg0NdT3zNcI08A"
CAVA_RSS_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CAVA_CHANNEL_ID}"
_ATOM = "{http://www.w3.org/2005/Atom}"
WORKFLOW = "cava"

_TOPICS: dict[str, tuple[str, ...]] = {
    "inflation": ("inflación", "inflacion", "cpi", "precios", "inflation"),
    "rates": ("tipos de interés", "tipos de interes", "tasas", "fed", "rates"),
    "dollar": ("dólar", "dolar", "dxy", "dollar"),
    "copper": ("cobre", "copper"),
    "gold": ("oro", "gold"),
    "liquidity": ("liquidez", "liquidity", "tga", "rrp"),
}
_SERIES = {
    "inflation": "CPIAUCSL",
    "rates": "DFF",
    "dollar": "DTWEXBGS",
    "copper": "PCOPPUSDM",
    "liquidity": "WALCL",
}


@dataclass(frozen=True)
class CavaVideo:
    video_id: str
    title: str
    published_at: datetime
    url: str


@dataclass(frozen=True)
class CavaCorroboration:
    evidence: tuple[Evidence, ...] = ()
    indicators: tuple[Mapping[str, Any], ...] = ()
    contradictions: tuple[Mapping[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    providers: tuple[ProviderHealth, ...] = ()


def parse_rss(xml_text: str) -> list[CavaVideo]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"invalid YouTube RSS XML: {exc}") from exc
    if root.tag != f"{_ATOM}feed":
        raise ValueError("YouTube RSS response is not an Atom feed")
    videos: dict[str, CavaVideo] = {}
    for entry in root.findall(f"{_ATOM}entry"):
        video_id = (entry.findtext(f"{_ATOM}id") or "").strip()
        if video_id.startswith("yt:video:"):
            video_id = video_id.removeprefix("yt:video:")
        title = (entry.findtext(f"{_ATOM}title") or "").strip()
        published = (entry.findtext(f"{_ATOM}published") or "").strip()
        if not video_id or not title or not published:
            continue
        try:
            published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if published_at.tzinfo is None:
                continue
            published_at = published_at.astimezone(UTC)
        except ValueError:
            continue
        videos[video_id] = CavaVideo(
            video_id=video_id,
            title=title,
            published_at=published_at,
            url=f"https://www.youtube.com/watch?v={video_id}",
        )
    if root.findall(f"{_ATOM}entry") and not videos:
        raise ValueError("YouTube RSS entries could not be normalized")
    return sorted(videos.values(), key=lambda item: item.published_at, reverse=True)


def _classify_claim(text: str) -> EvidenceKind:
    lowered = text.lower()
    if any(marker in lowered for marker in ("podría", "podria", "quizá", "quizas", "probablemente")):
        return EvidenceKind.HYPOTHESIS
    if any(marker in lowered for marker in ("porque", "por tanto", "esto significa", "implica")):
        return EvidenceKind.INFERENCE
    return EvidenceKind.UNKNOWN


def _topics_for(claim: str) -> list[str]:
    lowered = claim.lower()
    return [topic for topic, terms in _TOPICS.items() if any(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", lowered) for term in terms)]


def transcript_claims(video: CavaVideo, transcript: Transcript, decision_time: datetime) -> list[Evidence]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", transcript.text) if part.strip()]
    claims: list[Evidence] = []
    for index, sentence in enumerate(sentences, start=1):
        claims.append(
            Evidence(
                source=f"{transcript.source}.transcript",
                reference=f"cava-{video.video_id}-claim-{index}",
                claim=sentence,
                kind=_classify_claim(sentence),
                event_time=video.published_at,
                available_at=transcript.available_at,
                retrieved_at=transcript.available_at,
                decision_time=decision_time,
                provenance=Provenance.PROVIDER_RESULT,
                metadata={"video_id": video.video_id},
            )
        )
    return claims


def corroborate_claims(
    claims: list[Evidence],
    decision_time: datetime,
    *,
    series_fetcher: Callable[[str], Mapping[str, Any]] | None = None,
) -> CavaCorroboration:
    evidence: list[Evidence] = []
    indicators: list[Mapping[str, Any]] = []
    contradictions: list[Mapping[str, Any]] = []
    warnings: list[str] = []
    sources: list[str] = []
    providers: list[ProviderHealth] = []
    topics: dict[str, Evidence] = {}
    for claim in claims:
        for topic in _topics_for(claim.claim):
            if topic not in topics and len(topics) < 6:
                topics[topic] = claim
    for topic, transcript_claim in topics.items():
        series_id = _SERIES.get(topic)
        if not series_id:
            continue  # Explicitly excluded commentary; never a corroborated claim.
        try:
            raw, source = (series_fetcher(series_id), "injected") if series_fetcher else fetch_series(series_id, max_age_days={"inflation": 62, "copper": 62, "liquidity": 14}.get(topic, 7), now=decision_time)
            records = raw.get("records") if isinstance(raw, Mapping) else []
            observations = []
            for item in records or []:
                if not isinstance(item, Mapping):
                    continue
                date_text = _record_date(item)
                value = _record_value(item, series_id)
                if date_text is None or value is None:
                    continue
                try:
                    day = datetime.fromisoformat(str(date_text).replace("Z", "+00:00")).date()
                except ValueError:
                    continue
                if day <= decision_time.date():
                    observations.append((day, value))
            observations = sorted(observations)
            if not observations:
                raise RuntimeError("series returned no numeric observations")
            latest_date, latest = observations[-1]
            prior = observations[-2][1] if len(observations) > 1 else None
            stale_days = {"inflation": 62, "copper": 62, "liquidity": 14}.get(topic, 7)
            if (decision_time.date() - latest_date).days > stale_days:
                raise RuntimeError("latest source observation is stale")
            retrieved_raw = raw.get("retrieved_at")
            retrieved = (
                datetime.fromisoformat(str(retrieved_raw).replace("Z", "+00:00")) if retrieved_raw else None
            )
            if retrieved is None or retrieved.tzinfo is None:
                raise ValueError("source retrieval availability is unknown")
            source_label = f"{source}:{series_id}"
            providers.append(ProviderHealth(name=source_label, status=OperationalStatus.HEALTHY,
                                            retrieved_at=retrieved, coverage=f"{len(observations)} observations"))
            sources.append(source_label)
            evidence.append(
                Evidence(
                    source=source_label,
                    reference=f"cava-corroboration-{topic}",
                    claim=f"{series_id} latest observed value is {latest}",
                    kind=EvidenceKind.FACT,
                    event_time=datetime(latest_date.year, latest_date.month, latest_date.day, tzinfo=UTC),
                    observed_at=datetime(latest_date.year, latest_date.month, latest_date.day, tzinfo=UTC),
                    available_at=retrieved,
                    retrieved_at=retrieved,
                    decision_time=decision_time,
                    provenance=Provenance.PROVIDER_RESULT,
                    metadata={"topic": topic, "series_id": series_id,
                              "claim_references": [claim.reference for claim in claims if topic in _topics_for(claim.claim)],
                              "scope": "indicator context, not verification of forecasts or causal claims"},
                )
            )
            indicators.append({"topic": topic, "series_id": series_id, "latest": latest, "prior": prior})
            lowered = transcript_claim.claim.lower()
            claimed_up = any(re.search(r"(?<!\w)" + word + r"(?!\w)", lowered) for word in ("sube", "aumenta", "rise"))
            claimed_down = any(re.search(r"(?<!\w)" + word + r"(?!\w)", lowered) for word in ("baja", "cae", "fall"))
            if prior is not None and latest != prior and (claimed_up ^ claimed_down):
                observed = "up" if latest > prior else "down"
                claimed = "up" if claimed_up else "down"
                if observed != claimed:
                    contradictions.append(
                        {"topic": topic, "claim": transcript_claim.claim, "observed_direction": observed}
                    )
        except Exception as exc:
            providers.append(ProviderHealth(name=f"fred:{series_id}", status=OperationalStatus.UNAVAILABLE,
                                            failure_kind=type(exc).__name__, coverage="0 usable observations"))
            warnings.append(f"{topic}: {type(exc).__name__}")
    return CavaCorroboration(
        evidence=tuple(evidence),
        indicators=tuple(indicators),
        contradictions=tuple(contradictions),
        warnings=tuple(warnings),
        sources=tuple(sources),
        providers=tuple(providers),
    )


class CavaWorkflow:
    name = WORKFLOW

    def __init__(self, *, store: ResearchStore | None = None):
        self.store = store or ResearchStore()

    def _cursor(self) -> set[str]:
        payload = self.store.load_state("cava_cursor") or {}
        processed = payload.get("processed_video_ids") if isinstance(payload, Mapping) else []
        return {str(item) for item in processed or [] if str(item).strip()}

    def _save_cursor(self, processed: set[str], *, last: CavaVideo, decision_time: datetime) -> None:
        self.store.save_state(
            "cava_cursor",
            {
                "processed_video_ids": sorted(processed),
                "last_processed_video_id": last.video_id,
                "last_processed_at": decision_time.isoformat(),
            },
        )

    def _result(
        self,
        *,
        research: ResearchStatus,
        operational: OperationalStatus,
        started_at: datetime,
        payload: Mapping[str, Any],
        evidence: Iterable[Evidence] = (),
        warnings: Iterable[str] = (),
        providers: tuple[ProviderHealth, ...] = (),
        reasons: tuple[ResearchReason, ...] = (),
        decision_time: datetime | None = None,
    ) -> ResearchResult:
        result = ResearchResult(
            workflow=WORKFLOW,
            status=research,
            operational=OperationalReport(status=operational, providers=providers),
            decision_time=decision_time or started_at,
            started_at=started_at,
            completed_at=decision_time or started_at,
            mode=Mode.LIVE,
            payload={**dict(payload), "execution_enabled": False},
            evidence=tuple(evidence),
            warnings=tuple(warnings),
            reasons=reasons,
        )
        self.store.save_result(result)
        return result

    def unavailable(self, message: str, *, now: datetime | None = None) -> ResearchResult:
        started = now or datetime.now(UTC)
        return self._result(
            research=ResearchStatus.INSUFFICIENT_EVIDENCE,
            reasons=(ResearchReason(ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE, ("youtube.rss",), True),),
            operational=OperationalStatus.UNAVAILABLE,
            started_at=started,
            payload={"source": CAVA_RSS_URL, "videos_seen": 0, "cursor_advanced": False},
            warnings=(message,),
            providers=(
                ProviderHealth(name="youtube.rss", status=OperationalStatus.UNAVAILABLE, failure_kind="HTTPError", retrieved_at=started, coverage="0 usable feeds"),
            ),
        )

    def run(
        self,
        *,
        rss_xml: str,
        transcript_provider: TranscriptProvider,
        corroborate: Callable[..., Any] | None = None,
        now: datetime | None = None,
    ) -> ResearchResult:
        started = now or datetime.now(UTC)
        rss_health = ProviderHealth(name="youtube.rss", status=OperationalStatus.HEALTHY, retrieved_at=started)
        try:
            videos = parse_rss(rss_xml)
        except ValueError as exc:
            return self._result(
                research=ResearchStatus.INSUFFICIENT_EVIDENCE,
                reasons=(ResearchReason(ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE, ("valid youtube.rss",), True),),
                operational=OperationalStatus.UNAVAILABLE,
                started_at=started,
                payload={"source": CAVA_RSS_URL, "videos_seen": 0, "cursor_advanced": False},
                warnings=(str(exc),),
                providers=(ProviderHealth(name="youtube.rss", status=OperationalStatus.UNAVAILABLE, failure_kind="ParseError"),),
            )
        seen = self._cursor()
        new_videos = [video for video in videos if video.video_id not in seen
                      and timedelta(0) <= started - video.published_at < timedelta(days=3)]
        rss_evidence = Evidence(
            source="youtube.rss",
            reference="cava-rss",
            claim=f"RSS exposed {len(videos)} valid video entries",
            kind=EvidenceKind.FACT,
            event_time=started,
            available_at=started,
            retrieved_at=started,
            decision_time=started,
            provenance=Provenance.PROVIDER_RESULT,
        )
        if not new_videos:
            return self._result(
                research=ResearchStatus.NO_SETUP,
                operational=OperationalStatus.HEALTHY,
                started_at=started,
                payload={
                    "source": CAVA_RSS_URL,
                    "videos_seen": len(videos),
                    "new_videos": 0,
                    "outside_overlay_window": sum(not timedelta(0) <= started - v.published_at < timedelta(days=3) for v in videos),
                    "cursor_advanced": False,
                    "silent": True,
                },
                evidence=(rss_evidence,),
                providers=(rss_health,),
            )
        attempts = dict(self.store.load_state("cava_attempts") or {})
        video = min(new_videos, key=lambda item: int(attempts.get(item.video_id, 0)))
        attempts[video.video_id] = int(attempts.get(video.video_id, 0)) + 1
        self.store.save_state("cava_attempts", attempts)
        try:
            transcript = transcript_provider.fetch(video.video_id)
            if (not isinstance(transcript, Transcript) or not transcript.text.strip()
                    or transcript.available_at.tzinfo is None):
                raise TranscriptUnavailable("transcript content or availability is invalid")
        except (TranscriptUnavailable, ValueError, TypeError) as exc:
            return self._result(
                research=ResearchStatus.INSUFFICIENT_EVIDENCE,
                reasons=(ResearchReason(ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE, ("video transcript",), True),),
                operational=OperationalStatus.PARTIAL,
                started_at=started,
                payload={
                    "source": CAVA_RSS_URL,
                    "video": {"id": video.video_id, "title": video.title, "url": video.url},
                    "cursor_advanced": False,
                    "evidence_quality": "UNAVAILABLE",
                },
                evidence=(rss_evidence,),
                warnings=(f"transcript unavailable: {exc}",),
                providers=(
                    rss_health,
                    ProviderHealth(name="supadata", status=OperationalStatus.UNAVAILABLE, failure_kind="TranscriptUnavailable"),
                ),
            )
        decided = now or datetime.now(UTC)
        claims = transcript_claims(video, transcript, decided)
        if corroborate is None:
            corroboration = corroborate_claims(claims, decided)
        else:
            raw = corroborate(video, claims, decided)
            corroboration = raw if isinstance(raw, CavaCorroboration) else CavaCorroboration(evidence=tuple(raw or ()))
        decided = now or datetime.now(UTC)
        claims = [replace(item, decision_time=decided) for item in claims]
        corroboration = replace(corroboration, evidence=tuple(replace(item, decision_time=decided) for item in corroboration.evidence))
        warnings = list(corroboration.warnings)
        if not corroboration.evidence:
            warnings.append(
                "no eligible authoritative corroboration was found; transcript claims remain unverified commentary"
            )
        indicators = sorted({topic for claim in claims for topic in _topics_for(claim.claim)})
        required = set(indicators) & set(_SERIES)
        excluded = sorted(set(indicators) - required)
        covered = {
            item.metadata.get("topic")
            for item in corroboration.evidence
            if item.kind is EvidenceKind.FACT and item.availability.value == "ELIGIBLE"
            and item.provenance is Provenance.PROVIDER_RESULT
            and item.event_time is not None
            and decided - item.event_time <= timedelta(days={"inflation": 62, "copper": 62, "liquidity": 14}.get(item.metadata.get("topic"), 7))
        }
        context_validated = bool(
            claims
            and required
            and required <= covered
            and not corroboration.contradictions
            and video.published_at <= transcript.available_at <= decided
            and decided - video.published_at < timedelta(days=3)
        )
        payload = {
            "source": CAVA_RSS_URL,
            "video": {"id": video.video_id, "title": video.title, "url": video.url},
            "published_at": video.published_at.isoformat(),
            "transcript": {
                "source": transcript.source,
                "language": transcript.language,
                "characters": len(transcript.text),
            },
            "relevant_indicators": indicators,
            "required_indicators": sorted(required),
            "excluded_commentary_topics": excluded,
            "validation_scope": "supported indicator context only; transcript forecasts and causal claims remain unverified",
            "missing_indicators": sorted(required - covered),
            "contradictions": list(corroboration.contradictions),
            "corroboration_status": "VALIDATED"
            if context_validated
            else "PARTIAL"
            if corroboration.evidence
            else "UNAVAILABLE",
            "evidence_quality": "VALIDATED"
            if context_validated
            else "PARTIAL"
            if corroboration.evidence
            else "TRANSCRIPT_ONLY",
            "cursor_advanced": context_validated,
        }
        evidence = (replace(rss_evidence, decision_time=decided), *claims, *corroboration.evidence)
        failed = any(p.status is not OperationalStatus.HEALTHY for p in corroboration.providers)
        missing = sorted(required - covered)
        if not claims:
            missing.append("nonempty transcript claims")
        if not required:
            missing.append("supported indicator topics")
        if corroboration.contradictions:
            missing.append("noncontradictory indicator context")
        if not video.published_at <= transcript.available_at <= decided:
            missing.append("point-in-time transcript")
        if decided - video.published_at >= timedelta(days=3):
            missing.append("video younger than 3 days")
        result = self._result(
            research=ResearchStatus.SETUP_FOUND if context_validated else ResearchStatus.INSUFFICIENT_EVIDENCE,
            operational=OperationalStatus.PARTIAL if failed else OperationalStatus.HEALTHY,
            reasons=() if context_validated else (ResearchReason(
                ReasonCode.REQUIRED_PROVIDER_UNAVAILABLE if failed else ReasonCode.CORROBORATION_INSUFFICIENT,
                tuple(missing), failed or bool(required - covered)),),
            started_at=started,
            decision_time=decided,
            payload=payload,
            evidence=evidence,
            warnings=warnings,
            providers=(
                rss_health,
                ProviderHealth(name="supadata", status=OperationalStatus.HEALTHY, retrieved_at=transcript.available_at),
                *corroboration.providers,
            ),
        )
        if context_validated:
            self.store.save_context(
                "cava",
                {
                    "validated": True,
                    "source_video_id": video.video_id,
                    "published_at": video.published_at.isoformat(),
                    "validated_at": decided.isoformat(),
                    "expires_at": (video.published_at + timedelta(days=3)).isoformat(),
                    "corroboration_status": "VALIDATED",
                },
            )
            self._save_cursor(seen | {video.video_id}, last=video, decision_time=decided)
        else:
            previous = self.store.load_context("cava")
            if previous:
                self.store.save_context("cava", {**dict(previous), "validated": False})
        return result
