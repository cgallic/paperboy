"""Validated domain types for the fixture-driven Daily Intelligence Brief.

Every timestamp, ID, score, and policy knob is supplied by the caller. These
types do not read environment variables, the wall clock, a database, or the
network.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlsplit

DEFAULT_SECTION_ORDER = (
    "From your newsletters",
    "News",
    "Research",
    "Data watch",
    "Repo impact",
)


def _required_text(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def _optional_text(data: Mapping[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be null or a non-empty string")
    return value.strip()


def _text_tuple(data: Mapping[str, Any], key: str, *, required: bool = False) -> tuple[str, ...]:
    value = data.get(key, [])
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise ValueError(f"{key} must be a list of non-empty strings")
    out = tuple(v.strip() for v in value)
    if required and not out:
        raise ValueError(f"{key} must contain at least one value")
    return out


def _parse_datetime(value: Any, key: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{key} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{key} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _parse_date(value: Any, key: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{key} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be an ISO date") from exc


def _https_url(value: str, key: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError(f"{key} must be a public https URL")
    return value


@dataclass(frozen=True)
class RunConfig:
    edition_date: date
    period_start: datetime
    period_end: datetime
    min_relevance: int = 7
    max_items: int = 12
    max_per_source: int = 4
    max_repos: int = 5
    policy_version: str = "daily-brief-v1"
    schedule_label: str = "your configured schedule"
    section_order: tuple[str, ...] = DEFAULT_SECTION_ORDER
    sample: bool = True

    def __post_init__(self) -> None:
        if self.period_start >= self.period_end:
            raise ValueError("period_start must be earlier than period_end")
        if not 0 <= self.min_relevance <= 10:
            raise ValueError("min_relevance must be between 0 and 10")
        if not 1 <= self.max_items <= 12:
            raise ValueError("max_items must be between 1 and 12")
        if not 1 <= self.max_per_source <= self.max_items:
            raise ValueError("max_per_source must be between 1 and max_items")
        if not 0 <= self.max_repos <= 100:
            raise ValueError("max_repos must be between 0 and 100")
        if not self.policy_version.strip():
            raise ValueError("policy_version must be non-empty")
        if not self.section_order or len(set(self.section_order)) != len(self.section_order):
            raise ValueError("section_order must contain unique section names")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RunConfig:
        section_order = _text_tuple(data, "section_order") or DEFAULT_SECTION_ORDER
        return cls(
            edition_date=_parse_date(data.get("edition_date"), "edition_date"),
            period_start=_parse_datetime(data.get("period_start"), "period_start"),
            period_end=_parse_datetime(data.get("period_end"), "period_end"),
            min_relevance=int(data.get("min_relevance", 7)),
            max_items=int(data.get("max_items", 12)),
            max_per_source=int(data.get("max_per_source", 4)),
            max_repos=int(data.get("max_repos", 5)),
            policy_version=str(data.get("policy_version", "daily-brief-v1")).strip(),
            schedule_label=str(data.get("schedule_label", "your configured schedule")).strip(),
            section_order=section_order,
            sample=bool(data.get("sample", True)),
        )


@dataclass(frozen=True)
class RepoProfile:
    id: str
    full_name: str
    url: str
    summary: str
    languages: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RepoProfile:
        full_name = _required_text(data, "full_name")
        if full_name.count("/") != 1:
            raise ValueError("repo full_name must have owner/name form")
        url = _https_url(_required_text(data, "url"), "repo url")
        if urlsplit(url).netloc.lower() != "github.com":
            raise ValueError("repo url must use github.com")
        if data.get("visibility", "public") != "public":
            raise ValueError("only public repo profiles are accepted")
        return cls(
            id=_required_text(data, "id"),
            full_name=full_name,
            url=url,
            summary=_required_text(data, "summary"),
            languages=_text_tuple(data, "languages"),
            dependencies=_text_tuple(data, "dependencies"),
            topics=_text_tuple(data, "topics"),
        )


@dataclass(frozen=True)
class ExternalSignal:
    id: str
    source_kind: str
    source_label: str
    section: str
    occurred_at: datetime
    headline: str
    what_changed: str
    evidence_urls: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ExternalSignal:
        evidence = _text_tuple(data, "evidence_urls", required=True)
        return cls(
            id=_required_text(data, "id"),
            source_kind=_required_text(data, "source_kind").lower(),
            source_label=_required_text(data, "source_label"),
            section=_required_text(data, "section"),
            occurred_at=_parse_datetime(data.get("occurred_at"), "occurred_at"),
            headline=_required_text(data, "headline"),
            what_changed=_required_text(data, "what_changed"),
            evidence_urls=tuple(_https_url(url, "evidence URL") for url in evidence),
        )


@dataclass(frozen=True)
class ImpactVerdict:
    signal_id: str
    relevance: int
    why_it_matters: str
    next_step: str
    action_kind: str
    repo_id: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.relevance <= 10:
            raise ValueError("relevance must be between 0 and 10")
        if self.action_kind not in {"act", "watch"}:
            raise ValueError("action_kind must be act or watch")
        if self.action_kind == "watch" and "do nothing" not in self.next_step.lower():
            raise ValueError("watch next_step must explicitly say do nothing")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ImpactVerdict:
        return cls(
            signal_id=_required_text(data, "signal_id"),
            relevance=int(data.get("relevance", -1)),
            why_it_matters=_required_text(data, "why_it_matters"),
            next_step=_required_text(data, "next_step"),
            action_kind=_required_text(data, "action_kind").lower(),
            repo_id=_optional_text(data, "repo_id"),
        )


@dataclass(frozen=True)
class BriefItem:
    id: str
    rank: int
    section: str
    source_kind: str
    source_label: str
    signal_id: str
    occurred_at: datetime
    headline: str
    what_changed: str
    score: int
    why_it_matters: str
    next_step: str
    action_kind: str
    evidence_urls: tuple[str, ...]
    repo_id: str | None = None
    repo_full_name: str | None = None


@dataclass(frozen=True)
class BriefEdition:
    config: RunConfig
    status: str
    skip_reason: str | None
    candidate_hash: str
    items: tuple[BriefItem, ...]

    @property
    def is_quiet(self) -> bool:
        return self.status == "quiet"


@dataclass(frozen=True)
class BriefFixture:
    config: RunConfig
    repos: tuple[RepoProfile, ...]
    signals: tuple[ExternalSignal, ...]
    verdicts: tuple[ImpactVerdict, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BriefFixture:
        for key in ("config", "repos", "signals", "verdicts"):
            if key not in data:
                raise ValueError(f"fixture is missing {key}")
        repos_raw = data["repos"]
        signals_raw = data["signals"]
        verdicts_raw = data["verdicts"]
        if not all(isinstance(value, list) for value in (repos_raw, signals_raw, verdicts_raw)):
            raise ValueError("repos, signals, and verdicts must be lists")
        return cls(
            config=RunConfig.from_dict(data["config"]),
            repos=tuple(RepoProfile.from_dict(item) for item in repos_raw),
            signals=tuple(ExternalSignal.from_dict(item) for item in signals_raw),
            verdicts=tuple(ImpactVerdict.from_dict(item) for item in verdicts_raw),
        )
