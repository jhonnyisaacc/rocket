"""Cava RSS → transcript → claims → FRED corroboration. Optional overlay only."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
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
    "rates": ("tipo", "tasas", "fed", "bono", "interés", "interes", "rates", "yield"),
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


def parse_rss(xml_text: str) -> list[CavaVideo]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"invalid YouTube RSS XML: {exc}") from exc
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
    return [topic for topic, terms in _TOPICS.items() if any(term in lowered for term in terms)]


def transcript_claims(video: CavaVideo, transcript: Transcript, decision_time: datetime) -> list[Evidence]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", transcript.text) if part.strip()]
    claims: list[Evidence] = []
    for index, sentence in enumerate(sentences[:80], start=1):
        claims.append(
            Evidence(
                source="supadata.transcript",
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
    topics: dict[str, Evidence] = {}
    for claim in claims:
        for topic in _topics_for(claim.claim):
            if topic not in topics and len(topics) < 6:
                topics[topic] = claim
    for topic, transcript_claim in topics.items():
        series_id = _SERIES.get(topic)
        if not series_id:
            warnings.append(f"corroboration unavailable for {topic}: no supported reliable series")
            continue
        try:
            raw, source = (series_fetcher(series_id), "injected") if series_fetcher else fetch_series(series_id)
            records = raw.get("records") if isinstance(raw, Mapping) else []
            observations = []
            for item in records or []:
                if not isinstance(item, Mapping):
                    continue
                date_text = _record_date(item)
                value = _record_value(item, series_id)
                if date_text is None or value is None:
                    continue
                day = datetime.fromisoformat(str(date_text).replace("Z", "+00:00")).date()
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
                retrieved = decision_time
            source_label = f"{source}:{series_id}"
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
                    metadata={"topic": topic, "series_id": series_id},
                )
            )
            indicators.append({"topic": topic, "series_id": series_id, "latest": latest, "prior": prior})
            lowered = transcript_claim.claim.lower()
            claimed_up = any(word in lowered for word in ("alta", "sube", "aumenta", "rise", "high"))
            claimed_down = any(word in lowered for word in ("baja", "cae", "fall", "low"))
            if prior is not None and latest != prior and (claimed_up ^ claimed_down):
                observed = "up" if latest > prior else "down"
                claimed = "up" if claimed_up else "down"
                if observed != claimed:
                    contradictions.append(
                        {"topic": topic, "claim": transcript_claim.claim, "observed_direction": observed}
                    )
        except Exception as exc:
            warnings.append(f"{topic}: {exc}")
    return CavaCorroboration(
        evidence=tuple(evidence),
        indicators=tuple(indicators),
        contradictions=tuple(contradictions),
        warnings=tuple(warnings),
        sources=tuple(sources),
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
    ) -> ResearchResult:
        result = ResearchResult(
            workflow=WORKFLOW,
            status=research,
            operational=OperationalReport(status=operational, providers=providers),
            decision_time=started_at,
            started_at=started_at,
            completed_at=started_at,
            mode=Mode.LIVE,
            payload={**dict(payload), "execution_enabled": False},
            evidence=tuple(evidence),
            warnings=tuple(warnings),
        )
        self.store.save_result(result)
        return result

    def unavailable(self, message: str, *, now: datetime | None = None) -> ResearchResult:
        started = now or datetime.now(UTC)
        return self._result(
            research=ResearchStatus.INSUFFICIENT_EVIDENCE,
            operational=OperationalStatus.UNAVAILABLE,
            started_at=started,
            payload={"source": CAVA_RSS_URL, "videos_seen": 0, "cursor_advanced": False},
            warnings=(message,),
            providers=(
                ProviderHealth(name="youtube.rss", status=OperationalStatus.UNAVAILABLE, failure_kind="HTTPError"),
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
                operational=OperationalStatus.UNAVAILABLE,
                started_at=started,
                payload={"source": CAVA_RSS_URL, "videos_seen": 0, "cursor_advanced": False},
                warnings=(str(exc),),
                providers=(ProviderHealth(name="youtube.rss", status=OperationalStatus.UNAVAILABLE, failure_kind="ParseError"),),
            )
        seen = self._cursor()
        new_videos = [video for video in videos if video.video_id not in seen]
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
        except TranscriptUnavailable as exc:
            return self._result(
                research=ResearchStatus.INSUFFICIENT_EVIDENCE,
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
        claims = transcript_claims(video, transcript, started)
        if corroborate is None:
            corroboration = corroborate_claims(claims, started)
        else:
            raw = corroborate(video, claims, started)
            corroboration = raw if isinstance(raw, CavaCorroboration) else CavaCorroboration(evidence=tuple(raw or ()))
        warnings = list(corroboration.warnings)
        if not corroboration.evidence:
            warnings.append(
                "no eligible authoritative corroboration was found; transcript claims remain unverified commentary"
            )
        indicators = sorted({topic for claim in claims for topic in _topics_for(claim.claim)})
        covered = {
            item.metadata.get("topic")
            for item in corroboration.evidence
            if item.kind is EvidenceKind.FACT and item.availability.value == "ELIGIBLE"
        }
        context_validated = bool(
            claims
            and indicators
            and set(indicators) <= covered
            and not warnings
            and not corroboration.contradictions
            and video.published_at <= transcript.available_at <= started
            and started - video.published_at < timedelta(days=3)
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
        evidence = (rss_evidence, *claims, *corroboration.evidence)
        result = self._result(
            research=ResearchStatus.SETUP_FOUND if context_validated else ResearchStatus.INSUFFICIENT_EVIDENCE,
            operational=OperationalStatus.HEALTHY,
            started_at=started,
            payload=payload,
            evidence=evidence,
            warnings=warnings,
            providers=(
                rss_health,
                ProviderHealth(name="supadata", status=OperationalStatus.HEALTHY, retrieved_at=started),
            ),
        )
        if context_validated:
            self.store.save_context(
                "cava",
                {
                    "validated": True,
                    "source_video_id": video.video_id,
                    "published_at": video.published_at.isoformat(),
                    "validated_at": started.isoformat(),
                    "expires_at": (video.published_at + timedelta(days=3)).isoformat(),
                    "corroboration_status": "VALIDATED",
                },
            )
            self._save_cursor(seen | {video.video_id}, last=video, decision_time=started)
        else:
            previous = self.store.load_context("cava")
            if previous:
                self.store.save_context("cava", {**dict(previous), "validated": False})
        return result
